from pathlib import Path
import re
import pandas as pd

# Run this script from your Cyber Security Platform project root.
ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data" / "processed" / "cicids2017_cleaned.csv"
OUTPUT_DIR = ROOT / "data" / "test_csvs"

# Requested sizes for common categories. Rare categories use all available
# real examples rather than duplicating rows to inflate file size.
ROWS_PER_CATEGORY = {
    "BENIGN": 10000,
    "DoS": 10000,
    "DDoS": 10000,
    "Brute Force": 8000,
    "PortScan": 8000,
    "Bot": 5000,
    "XSS": 5000,
    "SQL Injection": 5000,
    "Infiltration": 5000,
    "Heartbleed": 5000,
}

RANDOM_STATE = 42
CHUNK_SIZE = 50000


def normalize_label(value):
    value = str(value).strip()
    return value.replace("\uFFFD", "-").replace("\u2013", "-").replace("\u2014", "-")


def map_attack_category(label):
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


def safe_filename(category):
    return re.sub(r"[^a-z0-9]+", "_", category.lower()).strip("_") + "_test.csv"


def main():
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Dataset not found: {SOURCE}\n"
            "Save this script in your project root, where the data folder is located."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    buckets = {category: [] for category in ROWS_PER_CATEGORY}
    counts = {category: 0 for category in ROWS_PER_CATEGORY}
    feature_columns = None

    print(f"Reading source dataset in chunks: {SOURCE}")
    for chunk_number, chunk in enumerate(
        pd.read_csv(SOURCE, chunksize=CHUNK_SIZE, low_memory=False), start=1
    ):
        chunk.columns = chunk.columns.astype(str).str.strip()
        chunk = chunk.loc[:, ~chunk.columns.duplicated()]
        chunk = chunk.drop(columns=["Fwd Header Length.1"], errors="ignore")

        if "Label" not in chunk.columns:
            raise ValueError("Expected a 'Label' column in the cleaned CICIDS2017 dataset.")

        if feature_columns is None:
            feature_columns = [c for c in chunk.columns if c != "Label"]

        chunk["_category"] = chunk["Label"].map(map_attack_category)

        for category, target_size in ROWS_PER_CATEGORY.items():
            if counts[category] >= target_size:
                continue

            matches = chunk.loc[chunk["_category"] == category, feature_columns]
            if matches.empty:
                continue

            remaining = target_size - counts[category]
            take = min(remaining, len(matches))
            if take < len(matches):
                matches = matches.sample(n=take, random_state=RANDOM_STATE + chunk_number)

            buckets[category].append(matches.copy())
            counts[category] += len(matches)

        print(f"Scanned chunk {chunk_number}; collected: " +
              ", ".join(f"{k}={v:,}" for k, v in counts.items()))

        if all(counts[k] >= ROWS_PER_CATEGORY[k] for k in ROWS_PER_CATEGORY):
            break

    category_frames = {}
    for category in ROWS_PER_CATEGORY:
        if buckets[category]:
            frame = pd.concat(buckets[category], ignore_index=True)
            # Keep the requested maximum. No duplicated rows are added.
            category_frames[category] = frame.head(ROWS_PER_CATEGORY[category])
        else:
            category_frames[category] = pd.DataFrame(columns=feature_columns or [])

        path = OUTPUT_DIR / safe_filename(category)
        category_frames[category].to_csv(path, index=False)
        print(f"Saved {path.name}: {len(category_frames[category]):,} rows")

    # Build a mixed file with up to 2,000 rows per available category.
    mixed_parts = []
    for category, frame in category_frames.items():
        if len(frame):
            mixed_parts.append(frame.sample(
                n=min(2000, len(frame)),
                random_state=RANDOM_STATE
            ))

    if mixed_parts:
        mixed = pd.concat(mixed_parts, ignore_index=True)
        mixed = mixed.sample(frac=1, random_state=RANDOM_STATE).reset_index(drop=True)
        mixed.to_csv(OUTPUT_DIR / "mixed_attacks_large.csv", index=False)
        print(f"Saved mixed_attacks_large.csv: {len(mixed):,} rows")
    else:
        print("WARNING: No matching categories were found; no mixed file was created.")

    print("\nDone. Upload files from:", OUTPUT_DIR)
    print("Note: these CSVs contain input features only, not ground-truth labels.")
    print("Predictions are not guaranteed to match the source category for every row.")


if __name__ == "__main__":
    main()
