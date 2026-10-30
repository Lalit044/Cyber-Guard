
from pathlib import Path
import sqlite3

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "data"
DATABASE_FILE = DATABASE_DIR / "prediction_history.db"


def get_connection():
    """Create a SQLite connection with row-based access."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        DATABASE_FILE,
        timeout=30,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database():
    """Create history tables if they do not already exist."""
    with get_connection() as connection:
        connection.execute("PRAGMA journal_mode = WAL")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                scanned_at TEXT NOT NULL,
                total_flows INTEGER NOT NULL DEFAULT 0,
                benign_count INTEGER NOT NULL DEFAULT 0,
                attack_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_id INTEGER NOT NULL,
                flow_index INTEGER,
                prediction TEXT,
                attack_type TEXT,
                prediction_confidence REAL,
                severity TEXT,
                review_priority TEXT,
                FOREIGN KEY (scan_id)
                    REFERENCES scans(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_predictions_scan_id
            ON predictions(scan_id)
            """
        )


def create_scan(filename, predictions):
    """
    Save one completed CSV scan and its predictions.

    predictions must be a pandas DataFrame containing the columns
    returned by backend.predictor.predict_dataframe().
    """
    required_columns = {
        "Prediction",
        "Attack Type",
        "Prediction Confidence",
        "Severity",
        "Review Priority",
    }

    missing = required_columns.difference(predictions.columns)
    if missing:
        raise ValueError(
            f"Prediction results are missing columns: {sorted(missing)}"
        )

    rows = []

    for position, (_, row) in enumerate(predictions.iterrows(), start=1):
        flow_index = row.get("Flow Index", position)

        try:
            flow_index = int(flow_index)
        except (TypeError, ValueError):
            flow_index = position

        confidence = row.get("Prediction Confidence")
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = None

        if confidence is not None and not (
            confidence == confidence
            and confidence not in (float("inf"), float("-inf"))
        ):
            confidence = None

        def safe_text(value):
            if value is None:
                return None
            try:
                if value != value:
                    return None
            except (TypeError, ValueError):
                pass
            return str(value)

        rows.append(
            (
                flow_index,
                safe_text(row.get("Prediction")),
                safe_text(row.get("Attack Type")),
                confidence,
                safe_text(row.get("Severity")),
                safe_text(row.get("Review Priority")),
            )
        )

    total_flows = len(rows)
    benign_count = sum(
        1 for row in rows
        if (row[1] or "").strip().upper() == "BENIGN"
    )
    attack_count = total_flows - benign_count

    from datetime import datetime, timezone

    scanned_at = datetime.now(timezone.utc).isoformat()

    # The scan summary and its predictions are committed together.
    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO scans (
                filename, scanned_at, total_flows,
                benign_count, attack_count
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                Path(filename).name,
                scanned_at,
                total_flows,
                benign_count,
                attack_count,
            ),
        )

        scan_id = cursor.lastrowid

        connection.executemany(
            """
            INSERT INTO predictions (
                scan_id, flow_index, prediction, attack_type,
                prediction_confidence, severity, review_priority
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (scan_id, *row)
                for row in rows
            ],
        )

    return {
        "id": scan_id,
        "filename": Path(filename).name,
        "scanned_at": scanned_at,
        "total_flows": total_flows,
        "benign_count": benign_count,
        "attack_count": attack_count,
    }


# Create the tables when this module is imported.
initialize_database()
