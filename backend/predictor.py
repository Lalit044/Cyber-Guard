from pathlib import Path

import joblib
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT / "artifacts"

BINARY_MODEL_PATH = ARTIFACTS_DIR / "binary_model.joblib"
ATTACK_MODEL_PATH = ARTIFACTS_DIR / "attack_model.joblib"


def load_model(path: Path) -> dict:
    """Load a saved model artifact."""
    if not path.exists():
        raise FileNotFoundError(
            f"Model not found: {path}. Train the models first."
        )

    artifact = joblib.load(path)

    if not isinstance(artifact, dict) or "pipeline" not in artifact:
        raise ValueError(f"Invalid model artifact: {path}")

    return artifact


# Load the models once when this module is imported.
binary_artifact = load_model(BINARY_MODEL_PATH)
attack_artifact = load_model(ATTACK_MODEL_PATH)

binary_model = binary_artifact["pipeline"]
attack_model = attack_artifact["pipeline"]

FEATURE_COLUMNS = binary_artifact["feature_columns"]
ATTACK_FEATURE_COLUMNS = attack_artifact["feature_columns"]

if FEATURE_COLUMNS != ATTACK_FEATURE_COLUMNS:
    raise ValueError(
        "Binary and attack models have different feature schemas."
    )


def prepare_features(data: pd.DataFrame) -> pd.DataFrame:
    """Validate uploaded features and arrange them in training order."""
    data = data.copy()
    data.columns = data.columns.astype(str).str.strip()

    # Never use ground-truth labels or derived labels as model inputs.
    forbidden = {
        "label",
        "attacktype",
        "binarylabel",
        "originallabel",
    }

    data = data.loc[
        :,
        [
            column for column in data.columns
            if column.lower() not in forbidden
        ],
    ]

    # CICIDS2017 can contain duplicated feature columns.
    data = data.loc[:, ~data.columns.duplicated()]

    missing = [
        column for column in FEATURE_COLUMNS
        if column not in data.columns
    ]

    if missing:
        preview = ", ".join(missing[:10])
        raise ValueError(
            f"CSV is missing {len(missing)} required feature columns. "
            f"Examples: {preview}"
        )

    # Ignore additional columns and match training feature order.
    data = data[FEATURE_COLUMNS].copy()

    for column in FEATURE_COLUMNS:
        data[column] = pd.to_numeric(
            data[column], errors="coerce"
        )

    data = data.replace([np.inf, -np.inf], np.nan)

    invalid_rows = data.isna().all(axis=1)

    if invalid_rows.any():
        raise ValueError(
            f"{int(invalid_rows.sum())} rows contain no usable features."
        )

    return data


def assess_severity(
    prediction: str,
    attack_type: str,
    confidence: float,
) -> tuple[str, str]:
    """
    Assign heuristic severity and review priority.

    These rules are triage suggestions, not verified incident severity.
    """
    prediction = prediction.strip().upper()
    attack = attack_type.strip().lower()

    if prediction == "BENIGN":
        if confidence < 75:
            return "Low", "Review Recommended"
        return "Informational", "Routine"

    if attack == "unclassified attack":
        return "High", "High Priority"

    # Starter heuristic; tune against validation data and your use case.
    if attack in {
        "infiltration",
        "heartbleed",
        "sql injection",
        "brute force",
    }:
        severity = "Critical" if confidence >= 80 else "High"

    elif attack in {"ddos", "dos"}:
        severity = "High" if confidence >= 70 else "Medium"

    elif confidence >= 90:
        severity = "High"

    elif confidence >= 70:
        severity = "Medium"

    else:
        severity = "Low"

    if severity == "Critical":
        priority = "Immediate Review"
    elif severity == "High":
        priority = "High Priority"
    elif severity == "Medium":
        priority = "Review Recommended"
    else:
        priority = "Monitor"

    return severity, priority


def predict_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """
    Return consistent binary and attack-category predictions,
    selected-class confidence, severity, and review priority.
    """
    if data.empty:
        raise ValueError("The uploaded CSV contains no data rows.")

    features = prepare_features(data)

    # Run both trained models.
    binary_predictions = binary_model.predict(features)
    attack_predictions = attack_model.predict(features)

    # Normalize binary output labels.
    binary_labels = np.array([
        "ATTACK" if str(label).strip().upper() == "ATTACK"
        else "BENIGN"
        for label in binary_predictions
    ])

    # Prevent contradictory combinations such as ATTACK / BENIGN.
    attack_types = []

    for binary_label, category in zip(
        binary_labels, attack_predictions
    ):
        category = str(category).strip()

        if binary_label == "BENIGN":
            attack_types.append("BENIGN")
        elif category.upper() == "BENIGN":
            attack_types.append("Unclassified Attack")
        else:
            attack_types.append(category)

    results = pd.DataFrame(index=data.index)
    results["Prediction"] = binary_labels
    results["Attack Type"] = attack_types

    # Confidence in the selected binary class.
    # Model probabilities are not guarantees of correctness.
    results["Prediction Confidence"] = np.nan

    if hasattr(binary_model, "predict_proba"):
        probabilities = binary_model.predict_proba(features)

        classes = [
            str(label).strip().upper()
            for label in binary_model.classes_
        ]

        attack_indices = [
            i for i, label in enumerate(classes)
            if label == "ATTACK"
        ]
        benign_indices = [
            i for i, label in enumerate(classes)
            if label == "BENIGN"
        ]

        if attack_indices and benign_indices:
            attack_probability = probabilities[:, attack_indices[0]]
            benign_probability = probabilities[:, benign_indices[0]]

            selected_confidence = np.where(
                binary_labels == "ATTACK",
                attack_probability,
                benign_probability,
            )

            results["Prediction Confidence"] = np.round(
                selected_confidence * 100, 2
            )

    # Add heuristic severity and review priority.
    severity_values = []
    priority_values = []

    for prediction, attack_type, confidence in zip(
        results["Prediction"],
        results["Attack Type"],
        results["Prediction Confidence"],
    ):
        confidence_value = (
            float(confidence) if pd.notna(confidence) else 0.0
        )

        severity, priority = assess_severity(
            str(prediction),
            str(attack_type),
            confidence_value,
        )

        severity_values.append(severity)
        priority_values.append(priority)

    results["Severity"] = severity_values
    results["Review Priority"] = priority_values

    results.index.name = "Flow Index"
    return results.reset_index()
