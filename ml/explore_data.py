
from pathlib import Path
from collections import Counter

import pandas as pd

# Project paths
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

csv_files = sorted(DATA_DIR.glob("*.csv"))

if not csv_files:
    raise FileNotFoundError(
        f"No CSV files found in: {DATA_DIR}"
    )

print(f"Dataset folder: {DATA_DIR}")
print(f"Number of CSV files: {len(csv_files)}")

label_counts = Counter()
total_rows = 0
reference_columns = None

for file_path in csv_files:
    print(f"\nProcessing: {file_path.name}")

    try:
        # Read the file in chunks to reduce memory usage
        chunks = pd.read_csv(
            file_path,
            chunksize=100_000,
            encoding="utf-8-sig",
            low_memory=False
        )

        file_rows = 0

        for chunk in chunks:
            # Normalize column names
            chunk.columns = (
                chunk.columns.astype(str).str.strip()
            )

            if reference_columns is None:
                reference_columns = list(chunk.columns)

                print("\nFEATURE COLUMNS:")
                for column in reference_columns:
                    print(f"  {column}")

            # Locate the target label column
            label_column = next(
                (
                    column for column in chunk.columns
                    if column.strip().lower() == "label"
                ),
                None
            )

            if label_column is None:
                raise ValueError(
                    f"Label column not found in {file_path.name}"
                )

            labels = (
                chunk[label_column]
                .astype("string")
                .str.strip()
                .fillna("MISSING")
            )

            label_counts.update(labels.value_counts().to_dict())

            file_rows += len(chunk)

        total_rows += file_rows
        print(f"Rows read: {file_rows:,}")

    except Exception as error:
        print(f"ERROR in {file_path.name}: {error}")
        raise

print("\n" + "=" * 50)
print("DATASET SUMMARY")
print("=" * 50)

print(f"Total CSV files: {len(csv_files)}")
print(f"Total rows: {total_rows:,}")
print(f"Unique labels: {len(label_counts)}")

print("\nLABEL DISTRIBUTION:")
for label, count in label_counts.most_common():
    print(f"{label}: {count:,}")

print("\nDataset exploration completed.")
