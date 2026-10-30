
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_FILE = PROCESSED_DIR / "cicids2017_cleaned.csv"
CHUNK_SIZE = 100_000


def clean_column_names(columns):
    return columns.astype(str).str.strip()


def main():
    csv_files = sorted(RAW_DIR.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {RAW_DIR}")

    total_rows = 0
    expected_columns = None
    first_write = True

    for file_path in csv_files:
        print(f"Processing: {file_path.name}")

        for chunk in pd.read_csv(
            file_path,
            chunksize=CHUNK_SIZE,
            encoding="utf-8-sig",
            low_memory=False,
        ):
            chunk.columns = clean_column_names(chunk.columns)

            # Remove duplicate feature names, keeping the first occurrence.
            chunk = chunk.loc[:, ~chunk.columns.duplicated()]

            if "Label" not in chunk.columns:
                raise ValueError(
                    f"Label column missing from {file_path.name}"
                )

            if expected_columns is None:
                expected_columns = list(chunk.columns)
            elif set(chunk.columns) != set(expected_columns):
                raise ValueError(
                    f"Column mismatch in {file_path.name}. "
                    "Inspect the CSV headers before combining files."
                )

            # Keep feature order consistent across all files.
            chunk = chunk[expected_columns]

            # Normalize labels without changing their meaning.
            chunk["Label"] = (
                chunk["Label"]
                .astype("string")
                .str.strip()
                .replace("", pd.NA)
            )

            # Convert features to numeric; malformed values become NaN.
            feature_columns = [
                col for col in chunk.columns if col != "Label"
            ]

            for col in feature_columns:
                chunk[col] = pd.to_numeric(
                    chunk[col], errors="coerce"
                )

            chunk[feature_columns] = chunk[
                feature_columns
            ].replace([float("inf"), float("-inf")], float("nan"))

            # Remove rows without usable target labels.
            chunk = chunk.dropna(subset=["Label"])

            # Keep rows with incomplete features for now.
            # Imputation will be fitted on training data only later.

            chunk.to_csv(
                OUTPUT_FILE,
                mode="w" if first_write else "a",
                header=first_write,
                index=False,
            )

            first_write = False
            total_rows += len(chunk)

    if total_rows == 0:
        raise ValueError("No usable rows were found.")

    print("\nPreprocessing completed.")
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Rows saved: {total_rows:,}")
    print(f"Feature columns: {len(expected_columns) - 1}")


if __name__ == "__main__":
    main()
