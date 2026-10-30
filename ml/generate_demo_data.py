from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = PROJECT_ROOT / "data" / "processed" / "cicids2017_cleaned.csv"
OUTPUT_DIR = PROJECT_ROOT / "data" / "demo"

SAMPLES_PER_CATEGORY = 1000
CHUNK_SIZE = 100_000

# Each entry defines the output filename and matching original labels.
CATEGORIES = {
    "01_benign.csv": ["benign"],
    "02_ddos.csv": ["ddos"],
    "03_dos.csv": ["dos"],
    "04_portscan.csv": ["portscan"],
    "05_brute_force.csv": ["brute force", "ftp-patator", "ssh-patator"],
    "06_sql_injection.csv": ["sql injection"],
    "07_xss.csv": ["xss"],
    "08_bot.csv": ["bot"],
    "09_infiltration.csv": ["infiltration"],
}

def normalize_label(value):
    return str(value).strip().lower().replace("\ufffd", "-")

def matches_category(label, category, patterns):
    label = normalize_label(label)

    if category == "01_benign.csv":
        return label == "benign"

    if category == "02_ddos.csv":
        return label == "ddos"

    if category == "03_dos.csv":
        return label.startswith("dos ")

    if category == "04_portscan.csv":
        return label == "portscan"

    if category == "05_brute_force.csv":
        return (
            "brute force" in label
            or label in ("ftp-patator", "ssh-patator")
        )

    if category == "06_sql_injection.csv":
        return "sql injection" in label

    if category == "07_xss.csv":
        return "xss" in label

    if category == "08_bot.csv":
        return label == "bot"

    if category == "09_infiltration.csv":
        return "infiltration" in label

    return any(pattern in label for pattern in patterns)

def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found: {INPUT_FILE}\n"
            "Run ml/preprocess.py first."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    samples = {name: [] for name in CATEGORIES}
    counts = {name: 0 for name in CATEGORIES}

    print("Reading CICIDS2017 dataset in chunks...")

    for chunk in pd.read_csv(INPUT_FILE, chunksize=CHUNK_SIZE, low_memory=False):
        if "Label" not in chunk.columns:
            raise ValueError("The input CSV must contain a Label column.")

        for filename, patterns in CATEGORIES.items():
            remaining = SAMPLES_PER_CATEGORY - counts[filename]
            if remaining <= 0:
                continue

            mask = chunk["Label"].map(
                lambda label: matches_category(label, filename, patterns)
            )
            selected = chunk.loc[mask].head(remaining)

            if not selected.empty:
                samples[filename].append(selected.copy())
                counts[filename] += len(selected)

        if all(count >= SAMPLES_PER_CATEGORY for count in counts.values()):
            break

    generated = {}

    for filename, frames in samples.items():
        if not frames:
            print(f"WARNING: No matching rows found for {filename}")
            continue

        result = pd.concat(frames, ignore_index=True)
        output_path = OUTPUT_DIR / filename
        result.to_csv(output_path, index=False)
        generated[filename] = result

        print(f"Created {filename}: {len(result):,} rows")

    # Mixed sample contains real records from all available categories.
    if generated:
        mixed_parts = []
        for frame in generated.values():
            mixed_parts.append(frame.sample(
                n=min(200, len(frame)),
                random_state=42
            ))

        mixed = pd.concat(mixed_parts, ignore_index=True)
        mixed = mixed.sample(frac=1, random_state=42).reset_index(drop=True)
        mixed_path = OUTPUT_DIR / "10_mixed_traffic.csv"
        mixed.to_csv(mixed_path, index=False)
        print(f"Created 10_mixed_traffic.csv: {len(mixed):,} rows")

    print(f"\nDemo files saved to: {OUTPUT_DIR}")
    print("Original feature columns and Label values have been preserved.")

if __name__ == "__main__":
    main()
