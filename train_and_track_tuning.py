"""Train IMDb sentiment models and log actual results in the local Django database."""

import argparse
import hashlib
import math
import os
from pathlib import Path
import platform
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

import joblib
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.pipeline import Pipeline


ROOT = Path(__file__).resolve().parent


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tune_classifier(model_name, classifier, x_train, y_train, args):
    """Choose a classifier setting using only folds from the training split."""
    try:
        import optuna
    except ImportError as error:
        raise SystemExit('Install Optuna first: python -m pip install "optuna==5.0.0"') from error

    parameter = "C" if model_name == "logistic_regression" else "alpha"
    cv = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=42)
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=42, n_startup_trials=2),
    )
    # Include the current setting, then let TPE choose subsequent candidates.
    initial_value = min(10.0, max(0.01, float(classifier.get_params()[parameter])))
    study.enqueue_trial({parameter: initial_value})
    started = perf_counter()
    with TemporaryDirectory(prefix="mlflowpro-cv-") as folder:
        memory = joblib.Memory(folder, verbose=0)

        def objective(trial):
            value = trial.suggest_float(parameter, 0.01, 10.0, log=True)
            print(
                f"[{model_name}] Trial {trial.number + 1}/{args.trials}: "
                f"{parameter}={value:.6g}", flush=True,
            )
            candidate = Pipeline([
                ("tfidf", TfidfVectorizer(max_features=args.max_features, ngram_range=(1, 2))),
                ("classifier", clone(classifier).set_params(**{parameter: value})),
            ], memory=memory)
            scores = cross_val_score(
                candidate, x_train, y_train, cv=cv, scoring="f1_macro",
                n_jobs=1, error_score="raise",
            )
            trial.set_user_attr("fold_f1_scores", scores.tolist())
            value = float(scores.mean())
            print(f"  Cross-validation macro F1: {value:.4f}", flush=True)
            return value

        study.optimize(objective, n_trials=args.trials)

    history = {
        "method": "Optuna TPE Bayesian optimization",
        "optuna_version": optuna.__version__,
        "objective": "mean cross-validation macro F1 on training data only",
        "cv_folds": args.folds, "seed": 42, "startup_trials": 2,
        "search_space": {parameter: {"low": 0.01, "high": 10.0, "log": True}},
        "n_trials": len(study.trials), "elapsed_seconds": perf_counter() - started,
        "best_trial": study.best_trial.number,
        "best_params": study.best_params,
        "best_cv_f1": float(study.best_value),
        "trials": [
            {"number": trial.number, "params": trial.params,
             "cv_f1": trial.value, "fold_f1_scores": trial.user_attrs.get("fold_f1_scores"),
             "state": trial.state.name}
            for trial in study.trials
        ],
    }
    print(f"Selected {model_name}: {study.best_params}; CV macro F1={study.best_value:.4f}", flush=True)
    return clone(classifier).set_params(**study.best_params), history


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "IMDB Dataset.csv")
    parser.add_argument("--model", choices=["both", "naive_bayes", "logistic_regression"], default="both")
    parser.add_argument("--max-features", type=int, default=50000)
    parser.add_argument("--c", type=float, default=1.0, help="Logistic Regression C")
    parser.add_argument("--alpha", type=float, default=1.0, help="Naive Bayes smoothing")
    parser.add_argument("--name", help="Optional experiment name")
    parser.add_argument("--optimize", action="store_true", help="Tune C or alpha with training-only TPE search")
    parser.add_argument("--trials", type=int, default=6, help="Trials per model (minimum 3)")
    parser.add_argument("--folds", type=int, default=3, help="Stratified training-only CV folds")
    args = parser.parse_args(argv)
    if args.max_features < 1 or not math.isfinite(args.c) or not math.isfinite(args.alpha) or not args.c > 0 or not args.alpha > 0:
        parser.error("max-features, c, and alpha must be positive.")
    if args.optimize and (args.trials < 3 or args.folds < 2):
        parser.error("Optimization requires at least 3 trials and 2 folds.")
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
    if args.optimize and y_train.value_counts().min() < args.folds:
        parser.error("There are too few training reviews per class for that many CV folds.")
    candidates = {
        "naive_bayes": MultinomialNB(alpha=args.alpha),
        "logistic_regression": LogisticRegression(C=args.c, max_iter=1000),
    }
    selected = candidates if args.model == "both" else {args.model: candidates[args.model]}
    completed = []
    for model_name, classifier in selected.items():
        tuning = None
        if args.optimize:
            classifier, tuning = tune_classifier(model_name, classifier, x_train, y_train, args)
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
        if tuning:
            parameters["optimization"] = {
                "method": tuning["method"], "best_params": tuning["best_params"],
                "best_cv_f1": tuning["best_cv_f1"], "cv_folds": tuning["cv_folds"],
                "n_trials": tuning["n_trials"],
            }
        completed.append((model_name, pipeline, parameters, metrics, training_time, tuning))
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
                name=args.name or f"IMDb {'TPE search' if args.optimize else 'benchmark'} {timezone.now():%Y-%m-%d %H:%M:%S}",
                dataset="IMDb Movie Reviews",
                description=(
                    "TF-IDF sentiment classification with a stratified 80/20 split (seed 42). "
                    + (f"Settings selected by {args.folds}-fold training-only TPE search." if args.optimize else "Fixed baseline settings.")
                ),
            )
            for model_name, pipeline, parameters, metrics, training_time, tuning in completed:
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
                if tuning:
                    version.provenance["optimization"] = tuning
                version.save()
    except Exception:
        for path in saved_paths:
            path.unlink(missing_ok=True)
        raise

    print(f"Saved experiment {experiment.pk}: {experiment.name}")
    for version in experiment.versions.all():
        print(f"Saved version: {version.model_name} -> {version.id}")
    print("Refresh the local dashboard to select the new versions and load their metrics.")
    return {"experiment_id": experiment.pk, "version_ids": [str(version.pk) for version in experiment.versions.all()]}


if __name__ == "__main__":
    main()
