
from io import BytesIO, StringIO
from pathlib import Path
from threading import Lock, Thread
from datetime import datetime, timezone
import json
import subprocess
import sys

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse

from backend.predictor import predict_dataframe
from backend.history_db import create_scan, get_connection


# --------------------------------------------------
# PROJECT PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAINING_SCRIPT = PROJECT_ROOT / "ml" / "train_model.py"
METRICS_FILE = PROJECT_ROOT / "artifacts" / "metrics.json"


# --------------------------------------------------
# TRAINING STATUS
# --------------------------------------------------

training_lock = Lock()

training_status = {
    "status": "idle",
    "message": "Training has not been started.",
    "started_at": None,
    "finished_at": None,
    "return_code": None,
    "logs": "",
}


def run_training():
    """Launch training and capture its output until it finishes."""
    started_at = datetime.now(timezone.utc).isoformat()

    with training_lock:
        training_status.update({
            "status": "running",
            "message": "Model training is starting.",
            "started_at": started_at,
            "finished_at": None,
            "return_code": None,
            "logs": f"Starting: {TRAINING_SCRIPT}\n",
        })

    process = None

    try:
        if not TRAINING_SCRIPT.is_file():
            raise FileNotFoundError(
                f"Training script not found: {TRAINING_SCRIPT}"
            )

        process = subprocess.Popen(
            [sys.executable, "-u", str(TRAINING_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        with training_lock:
            training_status["message"] = (
                f"Training process started (PID {process.pid})."
            )
            training_status["logs"] += (
                f"Training process PID: {process.pid}\n"
            )

        if process.stdout is not None:
            for line in process.stdout:
                with training_lock:
                    training_status["logs"] = (
                        training_status["logs"] + line
                    )[-20000:]

        return_code = process.wait()

        with training_lock:
            training_status["return_code"] = return_code
            training_status["finished_at"] = (
                datetime.now(timezone.utc).isoformat()
            )

            if return_code == 0:
                training_status["status"] = "completed"
                training_status["message"] = (
                    "Model training completed successfully."
                )
                training_status["logs"] += (
                    "\nTraining finished successfully.\n"
                )
            else:
                training_status["status"] = "failed"
                training_status["message"] = (
                    f"Training failed with exit code {return_code}."
                )
                training_status["logs"] += (
                    f"\nTraining process exited with code "
                    f"{return_code}.\n"
                )

    except Exception as error:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait()

        with training_lock:
            training_status["status"] = "failed"
            training_status["message"] = (
                f"Unable to run training: {error}"
            )
            training_status["finished_at"] = (
                datetime.now(timezone.utc).isoformat()
            )
            training_status["logs"] += f"\nERROR: {error}\n"

    finally:
        if process is not None and process.stdout is not None:
            process.stdout.close()


# --------------------------------------------------
# FASTAPI APPLICATION
# --------------------------------------------------

app = FastAPI(
    title="Cyber Security Platform API",
    description=(
        "CICIDS2017 network intrusion detection, model training, "
        "and prediction history API"
    ),
    version="1.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# --------------------------------------------------
# GENERAL ENDPOINTS
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Cyber Security Platform API is running",
        "docs": "/docs",
    }


@app.get("/api/health")
def health():
    return {"status": "healthy"}


# --------------------------------------------------
# CSV PREDICTION ENDPOINT
# --------------------------------------------------

@app.post("/api/predict")
async def predict_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file.",
        )

    try:
        contents = await file.read()

        if len(contents) > 100 * 1024 * 1024:
            raise HTTPException(
                status_code=413,
                detail="File is too large. Maximum size is 100 MB.",
            )

        if not contents:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        df = pd.read_csv(
            BytesIO(contents),
            encoding="utf-8-sig",
            low_memory=False,
        )

        if len(df) > 500_000:
            raise HTTPException(
                status_code=413,
                detail="Maximum 500,000 rows per upload.",
            )

        results = predict_dataframe(df)

        # Save the scan and predictions without blocking the CSV response
        # if history storage encounters an error.
        try:
            saved_scan = create_scan(file.filename, results)
            print(
                f"Saved prediction scan #{saved_scan['id']} "
                f"({saved_scan['total_flows']} flows)"
            )
        except Exception as history_error:
            print(
                "WARNING: Prediction succeeded, but history could not "
                f"be saved: {history_error}"
            )

        output = results.to_csv(index=False)

        return Response(
            content=output,
            media_type="text/csv",
            headers={
                "Content-Disposition":
                    'attachment; filename="predictions.csv"'
            },
        )

    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Prediction failed. Check the CSV format and server logs."
            ),
        ) from error
    finally:
        await file.close()


# --------------------------------------------------
# MODEL TRAINING ENDPOINTS
# --------------------------------------------------

@app.post("/api/train")
def start_training():
    """Start one training run in the background."""

    if not TRAINING_SCRIPT.is_file():
        raise HTTPException(
            status_code=500,
            detail=f"Training script not found: {TRAINING_SCRIPT}",
        )

    with training_lock:
        if training_status["status"] == "running":
            raise HTTPException(
                status_code=409,
                detail="Training is already running.",
            )

        training_status.update({
            "status": "running",
            "message": "Starting model training...",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "return_code": None,
            "logs": "Preparing training worker...\n",
        })

        try:
            thread = Thread(target=run_training, daemon=True)
            thread.start()
        except Exception as error:
            training_status.update({
                "status": "failed",
                "message": f"Could not start training: {error}",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "logs": f"ERROR: {error}\n",
            })
            raise HTTPException(
                status_code=500,
                detail="Could not start model training.",
            ) from error

    return {
        "message": "Model training has been started.",
        "status": "running",
    }


@app.get("/api/train/status")
def get_training_status():
    """Return the current training state and captured output."""
    with training_lock:
        return dict(training_status)


# --------------------------------------------------
# MODEL METRICS ENDPOINT
# --------------------------------------------------

@app.get("/api/train/metrics")
def get_training_metrics():
    """Return the metrics saved by the training script."""

    if not METRICS_FILE.is_file():
        raise HTTPException(
            status_code=404,
            detail="Metrics file not found. Train the model first.",
        )

    try:
        with METRICS_FILE.open("r", encoding="utf-8") as metrics_file:
            return json.load(metrics_file)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=500,
            detail="Could not read the model metrics file.",
        ) from error


# --------------------------------------------------
# PREDICTION HISTORY ENDPOINTS
# --------------------------------------------------

@app.get("/api/history")
def list_prediction_history(limit: int = 50, offset: int = 0):
    """List recent scans with summary statistics."""

    limit = max(1, min(limit, 200))
    offset = max(0, offset)

    try:
        with get_connection() as connection:
            total = connection.execute(
                "SELECT COUNT(*) FROM scans"
            ).fetchone()[0]

            rows = connection.execute(
                """
                SELECT id, filename, scanned_at, total_flows,
                       benign_count, attack_count
                FROM scans
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [dict(row) for row in rows],
        }

    except Exception as error:
        print(f"Could not read prediction history: {error}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve prediction history.",
        ) from error


@app.get("/api/history/{scan_id}")
def get_prediction_history_detail(scan_id: int):
    """Return one scan summary and its individual predictions."""

    try:
        with get_connection() as connection:
            scan = connection.execute(
                "SELECT * FROM scans WHERE id = ?",
                (scan_id,),
            ).fetchone()

            if scan is None:
                raise HTTPException(
                    status_code=404,
                    detail="Prediction scan not found.",
                )

            predictions = connection.execute(
                """
                SELECT flow_index, prediction, attack_type,
                       prediction_confidence, severity, review_priority
                FROM predictions
                WHERE scan_id = ?
                ORDER BY id
                """,
                (scan_id,),
            ).fetchall()

        return {
            "scan": dict(scan),
            "predictions": [dict(row) for row in predictions],
        }

    except HTTPException:
        raise
    except Exception as error:
        print(f"Could not read scan {scan_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve this scan's predictions.",
        ) from error


@app.get("/api/history/{scan_id}/download")
def download_prediction_history(scan_id: int):
    """Download previously saved predictions as CSV."""

    try:
        with get_connection() as connection:
            scan = connection.execute(
                "SELECT id FROM scans WHERE id = ?",
                (scan_id,),
            ).fetchone()

            if scan is None:
                raise HTTPException(
                    status_code=404,
                    detail="Prediction scan not found.",
                )

            rows = connection.execute(
                """
                SELECT flow_index AS "Flow Index",
                       prediction AS "Prediction",
                       attack_type AS "Attack Type",
                       prediction_confidence AS "Prediction Confidence",
                       severity AS "Severity",
                       review_priority AS "Review Priority"
                FROM predictions
                WHERE scan_id = ?
                ORDER BY id
                """,
                (scan_id,),
            ).fetchall()

        saved_df = pd.DataFrame([dict(row) for row in rows])
        csv_buffer = StringIO()
        saved_df.to_csv(csv_buffer, index=False)
        csv_buffer.seek(0)

        return StreamingResponse(
            iter([csv_buffer.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition":
                    f'attachment; filename="history_scan_{scan_id}.csv"'
            },
        )

    except HTTPException:
        raise
    except Exception as error:
        print(f"Could not download scan {scan_id}: {error}")
        raise HTTPException(
            status_code=500,
            detail="Could not download this scan's predictions.",
        ) from error
