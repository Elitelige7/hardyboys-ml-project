"""Queue local sentiment-tuning jobs and run them in a separate Celery worker."""

import argparse
import json
import os
from pathlib import Path
import sys
from uuid import UUID

from dotenv import load_dotenv

try:
    from celery import Celery
except ImportError as error:
    raise SystemExit('Install Celery: python -m pip install "celery[sqlalchemy]==5.6.3"') from error


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
load_dotenv(ROOT / "backend" / ".env")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MLFlowPro.settings")

# A single-computer development broker. Web and worker processes must share ROOT.
# A hosted multi-machine installation needs a shared broker and artifact store.
RUNTIME = ROOT / "local_jobs"
for directory in [RUNTIME, RUNTIME / "queue", RUNTIME / "control", RUNTIME / "processed"]:
    directory.mkdir(parents=True, exist_ok=True)

app = Celery(
    "MLFlowProLocalJobs",
    broker="filesystem://",
    backend=f"db+sqlite:///{(RUNTIME / 'results.sqlite3').as_posix()}",
)
app.conf.update(
    broker_transport_options={
        "data_folder_in": str(RUNTIME / "queue"),
        "data_folder_out": str(RUNTIME / "queue"),
        "control_folder": str(RUNTIME / "control"),
        "processed_folder": str(RUNTIME / "processed"),
        "store_processed": False,
        "polling_interval": 1.0,
    },
    broker_connection_retry_on_startup=True,
    task_default_queue="mlflowpro-tuning",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    result_expires=7 * 24 * 60 * 60,
    worker_prefetch_multiplier=1,
)


@app.task(bind=True, name="mlflowpro.tune_sentiment")
def tune_sentiment(self, model_name="logistic_regression", trials=6, max_features=50000):
    if model_name not in {"naive_bayes", "logistic_regression", "both"}:
        raise ValueError("Unknown sentiment model.")
    if not isinstance(trials, int) or not 3 <= trials <= 50:
        raise ValueError("Choose 3 to 50 trials.")
    if not isinstance(max_features, int) or not 1 <= max_features <= 50000:
        raise ValueError("Choose 1 to 50,000 features.")
    self.update_state(state="PROGRESS", meta={"message": "Tuning and training are running."})
    from train_and_track_tuning import main as train

    try:
        return train([
            "--model", model_name,
            "--optimize", "--trials", str(trials),
            "--max-features", str(max_features),
            "--name", f"Celery TPE run {self.request.id[:8]}",
        ])
    except SystemExit as error:
        # An argparse or setup error should mark the job FAILED, not exit the worker.
        raise RuntimeError(f"Training stopped during setup (exit {error.code}). Check the worker log.") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("worker", help="Run the separate local worker; leave this terminal open")
    enqueue = commands.add_parser("enqueue", help="Submit a tuning job and return immediately")
    enqueue.add_argument("--model", choices=["naive_bayes", "logistic_regression", "both"], default="logistic_regression")
    enqueue.add_argument("--trials", type=int, default=6)
    enqueue.add_argument("--max-features", type=int, default=50000)
    status = commands.add_parser("status", help="Read a job's state and final experiment/version IDs")
    status.add_argument("job_id", type=UUID)
    args = parser.parse_args()

    if args.command == "worker":
        return app.worker_main([
            "worker", "--pool=solo", "--concurrency=1", "--loglevel=INFO",
            "--without-gossip", "--without-mingle", "--without-heartbeat",
        ])

    if args.command == "enqueue":
        if not 3 <= args.trials <= 50 or not 1 <= args.max_features <= 50000:
            parser.error("Choose 3 to 50 trials and 1 to 50,000 features.")
        if not (ROOT / "train_and_track_tuning.py").is_file():
            parser.error("Place train_and_track_tuning.py beside background_jobs.py first.")
        if not (ROOT / "data" / "IMDB Dataset.csv").is_file():
            parser.error("Dataset not found: data/IMDB Dataset.csv")
        result = tune_sentiment.delay(args.model, args.trials, args.max_features)
        print(f"Queued job: {result.id}")
        print("The worker must be running in another terminal to execute this job.")
        print(f"Check status: python background_jobs.py status {result.id}")
        return 0

    result = app.AsyncResult(str(args.job_id))
    payload = {"job_id": str(args.job_id), "state": result.state}
    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    elif isinstance(result.info, dict):
        payload["progress"] = result.info
    if payload["state"] == "PENDING":
        payload["message"] = "Not started, or no result is stored for this job ID."
    print(json.dumps(payload, indent=2, default=str))
    return 1 if result.failed() else 0


if __name__ == "__main__":
    raise SystemExit(main())
