"""Train IMDb sentiment models and log actual results in the local Django database."""

import argparse
import hashlib
import os
from pathlib import Path
import platform
import sys
from time import perf_counter

import joblib
import pandas as pd
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parent


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "IMDB Dataset.csv")
    parser.add_argument("--model", choices=["both", "naive_bayes", "logistic_regression"], default="both")
    parser.add_argument("--max-features", type=int, default=50000)
    parser.add_argument("--c", type=float, default=1.0, help="Logistic Regression C")
    parser.add_argument("--alpha", type=float, default=1.0, help="Naive Bayes smoothing")
    parser.add_argument("--name", help="Optional experiment name")
    args = parser.parse_args()
    if args.max_features < 1 or not args.c > 0 or not args.alpha > 0:
        parser.error("max-features, c, and alpha must be positive.")
    if not args.dataset.is_file():
        parser.error(f"Dataset not found: {args.dataset}")

    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MLFlowPro.settings")
    import django
    django.setup()
    from django.db import connection, transaction
    from django.utils import timezone
    from experiments.models import Experiment, ExperimentResult, ModelSettings, ModelVersion

    # Check the database before spending time on training.
    connection.ensure_connection()
    ModelVersion.objects.exists()

    dataset_hash = file_sha256(args.dataset)
    frame = pd.read_csv(args.dataset, usecols=["review", "sentiment"])
    frame = frame.dropna().drop_duplicates(subset=["review"])
    if set(frame["sentiment"]) != {"positive", "negative"}:
        parser.error("The sentiment column must contain positive and negative labels.")
    if frame["sentiment"].value_counts().min() < 5:
        parser.error("Provide at least five reviews of each sentiment.")

    x_train, x_test, y_train, y_test = train_test_split(
        frame["review"], frame["sentiment"],
        test_size=0.2, random_state=42, stratify=frame["sentiment"],
    )
    candidates = {
        "naive_bayes": MultinomialNB(alpha=args.alpha),
        "logistic_regression": LogisticRegression(C=args.c, max_iter=1000),
    }
    selected = candidates if args.model == "both" else {args.model: candidates[args.model]}
    completed = []
    for model_name, classifier in selected.items():
        print(f"Training {model_name} on {len(x_train):,} reviews...", flush=True)
        pipeline = Pipeline([
            ("tfidf", TfidfVectorizer(max_features=args.max_features, ngram_range=(1, 2))),
            ("classifier", classifier),
        ])
        started = perf_counter()
        pipeline.fit(x_train, y_train)
        training_time = perf_counter() - started
        test_predictions = pipeline.predict(x_test)
        train_predictions = pipeline.predict(x_train)
        metrics = {
            "accuracy": float(accuracy_score(y_test, test_predictions)),
            "f1_score": float(f1_score(y_test, test_predictions, average="macro")),
            "train_accuracy": float(accuracy_score(y_train, train_predictions)),
            "train_f1_score": float(f1_score(y_train, train_predictions, average="macro")),
            "confusion_matrix": confusion_matrix(
                y_test, test_predictions, labels=["negative", "positive"]
            ).tolist(),
            "confusion_matrix_labels": ["negative", "positive"],
            "f1_average": "macro",
        }
        parameters = {
            "max_features": args.max_features, "ngram_range": [1, 2],
            "classifier": classifier.get_params(),
        }
        completed.append((model_name, pipeline, parameters, metrics, training_time))
        print(f"  Test accuracy: {metrics['accuracy']:.4f}; macro F1: {metrics['f1_score']:.4f}", flush=True)

    provenance = {
        "dataset_file": args.dataset.name, "dataset_sha256": dataset_hash,
        "preprocessing": "Select review/sentiment, drop missing values and duplicate review texts",
        "dataset_rows": len(frame), "train_rows": len(x_train), "test_rows": len(x_test),
        "random_state": 42, "test_size": 0.2, "stratified": True,
        "vectorizer_fit": "training reviews only",
        "train_indices_sha256": hashlib.sha256(
            ",".join(map(str, x_train.index)).encode()
        ).hexdigest(),
        "test_indices_sha256": hashlib.sha256(
            ",".join(map(str, x_test.index)).encode()
        ).hexdigest(),
        "python_version": platform.python_version(), "sklearn_version": sklearn.__version__,
        "pandas_version": pd.__version__, "joblib_version": joblib.__version__,
        "evaluation_status": "Measured on the held-out 20% test split during this run",
    }
    store = ROOT / "models" / "versions"
    store.mkdir(parents=True, exist_ok=True)
    saved_paths = []
    try:
        with transaction.atomic():
            experiment = Experiment.objects.create(
                name=args.name or f"IMDb benchmark {timezone.now():%Y-%m-%d %H:%M:%S}",
                dataset="IMDb Movie Reviews",
                description="TF-IDF sentiment classification with a stratified 80/20 split (seed 42).",
            )
            for model_name, pipeline, parameters, metrics, training_time in completed:
                ModelSettings.objects.create(
                    experiment=experiment, model_name=model_name,
                    max_features=args.max_features, ngram_min=1, ngram_max=2,
                    parameters=parameters,
                )
                ExperimentResult.objects.create(
                    experiment=experiment, model_name=model_name,
                    accuracy=metrics["accuracy"], f1_score=metrics["f1_score"],
                    training_time=training_time,
                )
                version = ModelVersion(
                    experiment=experiment, model_name=model_name,
                    parameters=parameters, metrics=metrics,
                )
                version.artifact = f"{version.id}.joblib"
                artifact_path = store / version.artifact
                saved_paths.append(artifact_path)
                joblib.dump(pipeline, artifact_path)
                version.provenance = {
                    **provenance, "artifact_sha256": file_sha256(artifact_path),
                }
                version.save()
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise

    print(f"Saved experiment {experiment.pk}: {experiment.name}")
    for version in experiment.versions.all():
        print(f"Saved version: {version.model_name} -> {version.id}")
    print("Refresh the local dashboard to select the new versions and load their metrics.")


if __name__ == "__main__":
    main()
