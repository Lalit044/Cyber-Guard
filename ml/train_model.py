from pathlib import Path
import json
import warnings

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

warnings.filterwarnings("ignore", category=UserWarning)

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "processed" / "cicids2017_cleaned.csv"
ARTIFACTS_DIR = ROOT / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

# With limited RAM, sample a smaller number of rows per attack category.
SAMPLE_PER_CLASS = 8_000
CHUNK_SIZE = 50_000
TEST_SIZE = 0.20


def normalize_label(label):
    """Normalize Unicode punctuation and whitespace in labels."""
    label = str(label).strip()
    label = label.replace("\uFFFD", "-")
    label = label.replace("\u2013", "-")
    label = label.replace("\u2014", "-")
    return label


def map_attack_category(label):
    """Map original CICIDS2017 labels to broader attack categories."""
    value = normalize_label(label).lower()

    if value == "benign":
        return "BENIGN"
    if "ddos" in value:
        return "DDoS"
    if value.startswith("dos ") or value == "dos":
        return "DoS"
    if "patator" in value or "brute force" in value:
        return "Brute Force"
    if "sql injection" in value:
        return "SQL Injection"
    if "xss" in value:
        return "XSS"
    if "portscan" in value:
        return "PortScan"
    if "infiltration" in value:
        return "Infiltration"
    if "heartbleed" in value:
        return "Heartbleed"
    if "bot" in value:
        return "Bot"

    return "Other Attack"


def build_pipeline():
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "model",
                RandomForestClassifier(
                    n_estimators=100,
                    class_weight="balanced_subsample",
                    random_state=RANDOM_STATE,
                    # Limit parallel workers to reduce peak RAM use.
                    n_jobs=1,
                    min_samples_leaf=2,
                ),
            ),
        ]
    )


def load_sample_by_category():
    """
    Read the CSV in chunks and keep a bounded sample per attack category.
    This avoids loading the complete 0.9 GB CSV into RAM at once.
    """
    if not DATA_FILE.is_file():
        raise FileNotFoundError(f"Dataset not found: {DATA_FILE}")

    print("Reading dataset in memory-limited chunks...", flush=True)

    samples = {}
    total_rows = 0
    expected_columns = None

    for chunk_number, chunk in enumerate(
        pd.read_csv(DATA_FILE, low_memory=False, chunksize=CHUNK_SIZE),
        start=1,
    ):
        chunk.columns = chunk.columns.astype(str).str.strip()
        chunk = chunk.loc[:, ~chunk.columns.duplicated()]
        chunk = chunk.drop(columns=["Fwd Header Length.1"], errors="ignore")

        if "Label" not in chunk.columns:
            raise ValueError("The dataset must contain a Label column.")

        if expected_columns is None:
            expected_columns = list(chunk.columns)

        chunk["OriginalLabel"] = chunk["Label"].map(normalize_label)
        chunk["AttackType"] = chunk["OriginalLabel"].map(map_attack_category)
        chunk["BinaryLabel"] = np.where(
            chunk["AttackType"] == "BENIGN", "BENIGN", "ATTACK"
        )

        total_rows += len(chunk)

        # Keep only the rows needed for training; never accumulate the full CSV.
        for category, group in chunk.groupby("AttackType", sort=False):
            existing = samples.get(category)

            if existing is None or existing.empty:
                combined = group
            else:
                combined = pd.concat([existing, group], ignore_index=True)

            if len(combined) > SAMPLE_PER_CLASS:
                combined = combined.sample(
                    n=SAMPLE_PER_CLASS,
                    random_state=RANDOM_STATE,
                )

            samples[category] = combined.reset_index(drop=True)

        print(
            f"Read chunk {chunk_number}; scanned {total_rows:,} rows.",
            flush=True,
        )

        del chunk

    if not samples:
        raise ValueError("No rows were loaded from the dataset.")

    sampled = pd.concat(samples.values(), ignore_index=True)
    sampled = sampled.loc[:, ~sampled.columns.duplicated()]

    print(f"Total rows scanned: {total_rows:,}", flush=True)
    print(f"Rows selected for training/evaluation: {len(sampled):,}", flush=True)

    return sampled, total_rows


def main():
    sampled, full_rows = load_sample_by_category()

    feature_columns = [
        col for col in sampled.columns
        if col not in {
            "Label",
            "OriginalLabel",
            "AttackType",
            "BinaryLabel",
        }
    ]

    if not feature_columns:
        raise ValueError("No feature columns were found.")

    # Convert features to numeric values and replace infinities.
    # CICIDS2017 traffic features should be numeric.
    X = sampled[feature_columns].apply(pd.to_numeric, errors="coerce")
    X = X.replace([np.inf, -np.inf], np.nan)
    y_binary = sampled["BinaryLabel"]
    y_attack = sampled["AttackType"]

    print(f"Feature count: {len(feature_columns)}", flush=True)
    print("\nAttack category distribution:", flush=True)
    print(y_attack.value_counts().to_string(), flush=True)

    # A stratified split requires at least two examples in every class.
    counts = y_attack.value_counts()
    if (counts < 2).any():
        rare = counts[counts < 2].to_dict()
        raise ValueError(
            "Cannot make a stratified train/test split because these "
            f"categories have fewer than 2 sampled rows: {rare}"
        )

    X_train, X_test, yb_train, yb_test, ya_train, ya_test = train_test_split(
        X,
        y_binary,
        y_attack,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y_attack,
    )

    print("\nTraining binary classifier...", flush=True)
    binary_model = build_pipeline()
    binary_model.fit(X_train, yb_train)
    binary_predictions = binary_model.predict(X_test)

    print("\nBinary classification report:", flush=True)
    print(
        classification_report(
            yb_test,
            binary_predictions,
            zero_division=0,
        ),
        flush=True,
    )
    binary_accuracy = accuracy_score(yb_test, binary_predictions)
    print(f"Binary accuracy: {binary_accuracy:.4f}", flush=True)

    print("\nTraining attack-type classifier...", flush=True)
    attack_model = build_pipeline()
    attack_model.fit(X_train, ya_train)
    attack_predictions = attack_model.predict(X_test)

    print("\nAttack-type classification report:", flush=True)
    print(
        classification_report(
            ya_test,
            attack_predictions,
            zero_division=0,
        ),
        flush=True,
    )
    attack_accuracy = accuracy_score(ya_test, attack_predictions)
    print(f"Attack accuracy: {attack_accuracy:.4f}", flush=True)

    # Save to temporary files first, then replace the previous artifacts.
    binary_temp = ARTIFACTS_DIR / "binary_model.joblib.tmp"
    attack_temp = ARTIFACTS_DIR / "attack_model.joblib.tmp"
    metrics_temp = ARTIFACTS_DIR / "metrics.json.tmp"

    joblib.dump(
        {
            "pipeline": binary_model,
            "feature_columns": feature_columns,
            "classes": list(binary_model.classes_),
        },
        binary_temp,
    )

    joblib.dump(
        {
            "pipeline": attack_model,
            "feature_columns": feature_columns,
            "classes": list(attack_model.classes_),
        },
        attack_temp,
    )

    metrics = {
        "dataset": "CICIDS2017",
        "full_rows": int(full_rows),
        "sampled_rows": int(len(sampled)),
        "feature_count": len(feature_columns),
        "binary_accuracy": float(binary_accuracy),
        "attack_accuracy": float(attack_accuracy),
        "attack_categories": sorted(y_attack.unique().tolist()),
        "binary_report": classification_report(
            yb_test,
            binary_predictions,
            output_dict=True,
            zero_division=0,
        ),
        "attack_report": classification_report(
            ya_test,
            attack_predictions,
            output_dict=True,
            zero_division=0,
        ),
    }

    with metrics_temp.open("w", encoding="utf-8") as file:
        json.dump(metrics, file, indent=2)

    binary_temp.replace(ARTIFACTS_DIR / "binary_model.joblib")
    attack_temp.replace(ARTIFACTS_DIR / "attack_model.joblib")
    metrics_temp.replace(ARTIFACTS_DIR / "metrics.json")

    print("\nTraining complete.", flush=True)
    print(f"Saved binary model: {ARTIFACTS_DIR / 'binary_model.joblib'}", flush=True)
    print(f"Saved attack model: {ARTIFACTS_DIR / 'attack_model.joblib'}", flush=True)
    print(f"Saved metrics: {ARTIFACTS_DIR / 'metrics.json'}", flush=True)


if __name__ == "__main__":
    main()
