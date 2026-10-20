from pathlib import Path
import hashlib
import os
import shutil
import sys

import django
import joblib

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MLFlowPro.settings")
django.setup()

from experiments.models import Experiment, ModelVersion

store = ROOT / "models" / "versions"
store.mkdir(parents=True, exist_ok=True)
experiment, _ = Experiment.objects.get_or_create(
    name="Imported IMDb models",
    defaults={"dataset": "IMDb Movie Reviews"},
)

for name in ["naive_bayes", "logistic_regression"]:
    source = ROOT / "models" / f"{name}.joblib"
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    existing = ModelVersion.objects.filter(
        model_name=name, provenance__artifact_sha256=digest
    ).first()

    if existing:
        if not (store / existing.artifact).is_file():
            shutil.copy2(source, store / existing.artifact)
        print(f"Already registered: {name} -> {existing.id}")
        continue

    pipeline = joblib.load(source)
    vectorizer = pipeline.named_steps["tfidf"]
    classifier = pipeline.named_steps["classifier"]
    parameters = {
        "max_features": vectorizer.max_features,
        "ngram_range": list(vectorizer.ngram_range),
    }
    for key in ["C", "alpha", "max_iter", "solver"]:
        if hasattr(classifier, key):
            parameters[key] = getattr(classifier, key)

    version = ModelVersion(
        experiment=experiment,
        model_name=name,
        parameters=parameters,
        metrics={},
        provenance={
            "source_file": source.name,
            "artifact_sha256": digest,
            "evaluation_status": "Original evaluation log needs verification",
        },
    )
    version.artifact = f"{version.id}.joblib"
    shutil.copy2(source, store / version.artifact)
    version.save()
    print(f"Registered: {name} -> {version.id}")
