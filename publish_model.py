"""Export a measured model version to Git, or restore published versions on Render."""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
from uuid import UUID, uuid4


ROOT = Path(__file__).resolve().parent


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_verified(source, target, expected_hash):
    if sha256(source) != expected_hash:
        raise ValueError(f"Published model file failed its hash check: {source.name}")
    if target.is_file() and sha256(target) == expected_hash:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f"{target.name}.{uuid4().hex}.tmp")
    try:
        shutil.copy2(source, temporary)
        if sha256(temporary) != expected_hash:
            raise ValueError("Model copy failed its hash check.")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def validate(payload):
    if payload.get("format") != 1:
        raise ValueError("Unknown published-model format.")
    payload["version_id"] = str(UUID(payload["version_id"]))
    if payload["model_name"] not in {"naive_bayes", "logistic_regression"}:
        raise ValueError("Unknown model name.")
    for field in ["accuracy", "f1_score"]:
        value = payload["metrics"][field]
        if not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Invalid measured {field}.")
        if abs(payload["result"][field] - value) > 1e-12:
            raise ValueError(f"Result and model-version {field} do not match.")
    elapsed = payload["result"]["training_time"]
    if not isinstance(elapsed, (float, int)) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("Invalid training duration.")
    digest = payload["artifact_sha256"]
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError("Invalid model hash.")
    if payload["provenance"].get("artifact_sha256") != digest:
        raise ValueError("The provenance and package model hashes do not match.")
    if not isinstance(payload["parameters"], dict):
        raise ValueError("Invalid parameters.")
    for field in ["name", "dataset"]:
        if not isinstance(payload["experiment"][field], str) or len(payload["experiment"][field]) > 200:
            raise ValueError(f"Invalid experiment {field}.")
    return payload


def export_version(version_id):
    from experiments.models import ExperimentResult, ModelVersion

    version = ModelVersion.objects.select_related("experiment").get(pk=version_id)
    result = ExperimentResult.objects.filter(
        experiment=version.experiment, model_name=version.model_name,
    ).order_by("-created_at").first()
    if not result:
        raise ValueError("This version has no measured experiment result to publish.")
    if version.artifact != f"{version.id}.joblib":
        raise ValueError("Expected the UUID-named snapshot created by the training command.")
    source = ROOT / "models" / "versions" / version.artifact
    digest = sha256(source)
    if digest != version.provenance.get("artifact_sha256"):
        raise ValueError("The saved file differs from the registered version.")
    payload = validate({
        "format": 1, "version_id": str(version.id), "model_name": version.model_name,
        "original_created_at": version.created_at.isoformat(),
        "experiment": {
            "name": version.experiment.name,
            "description": version.experiment.description,
            "dataset": version.experiment.dataset,
        },
        "parameters": version.parameters,
        "metrics": version.metrics,
        "provenance": version.provenance,
        "artifact_sha256": digest,
        "result": {
            "accuracy": result.accuracy, "f1_score": result.f1_score,
            "training_time": result.training_time,
        },
    })
    content = json.dumps(payload, indent=2, allow_nan=False) + "\n"
    folder = ROOT / "published_models" / str(version.id)
    folder.mkdir(parents=True, exist_ok=True)
    copy_verified(source, folder / "model.joblib", digest)
    (folder / "manifest.json").write_text(content, encoding="utf-8")
    print(f"Exported version {version.id} to {folder}")
    print(f"Measured accuracy: {result.accuracy:.2%}; macro F1: {result.f1_score:.2%}")
    print("The published_models folder contains the selected model and metadata; commit it with Git.")


def restore_versions():
    from django.db import transaction
    from experiments.models import Experiment, ExperimentResult, ModelSettings, ModelVersion

    manifests = sorted((ROOT / "published_models").glob("*/manifest.json"))
    if not manifests:
        print("No published model packages found.")
        return
    for manifest in manifests:
        payload = validate(json.loads(manifest.read_text(encoding="utf-8")))
        source = manifest.parent / "model.joblib"
        if sha256(source) != payload["artifact_sha256"]:
            raise ValueError(f"Published model file failed its hash check: {manifest.parent.name}")
        existing = ModelVersion.objects.filter(pk=payload["version_id"]).first()
        if existing:
            if (
                existing.model_name != payload["model_name"]
                or existing.parameters != payload["parameters"]
                or existing.metrics != payload["metrics"]
                or existing.provenance.get("artifact_sha256") != payload["artifact_sha256"]
                or existing.artifact != f"{existing.id}.joblib"
            ):
                raise ValueError("An existing version with this ID has different recorded data.")
            target = ROOT / "models" / "versions" / existing.artifact
            copy_verified(source, target, payload["artifact_sha256"])
            print(f"Already registered; verified model file: {existing.id}")
            continue

        target = ROOT / "models" / "versions" / f"{payload['version_id']}.joblib"
        file_existed = target.exists()
        copy_verified(source, target, payload["artifact_sha256"])
        try:
            with transaction.atomic():
                experiment = Experiment.objects.create(**payload["experiment"])
                parameters = payload["parameters"]
                ngrams = parameters.get("ngram_range", [1, 2])
                ModelSettings.objects.create(
                    experiment=experiment, model_name=payload["model_name"],
                    max_features=parameters.get("max_features", 50000),
                    ngram_min=ngrams[0], ngram_max=ngrams[1], parameters=parameters,
                )
                ExperimentResult.objects.create(
                    experiment=experiment, model_name=payload["model_name"], **payload["result"],
                )
                ModelVersion.objects.create(
                    id=payload["version_id"], experiment=experiment,
                    model_name=payload["model_name"], parameters=parameters,
                    metrics=payload["metrics"], artifact=target.name,
                    provenance={
                        **payload["provenance"],
                        "original_created_at": payload["original_created_at"],
                    },
                )
        except Exception:
            if not file_existed:
                target.unlink(missing_ok=True)
            raise
        print(f"Restored {payload['model_name']} version {payload['version_id']} with its measured results.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="Package one measured local version for Git")
    export.add_argument("version_id", type=UUID)
    commands.add_parser("restore", help="Restore packaged versions and results during deployment")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / "backend"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "MLFlowPro.settings")
    import django
    django.setup()
    if args.command == "export":
        export_version(args.version_id)
    else:
        restore_versions()


if __name__ == "__main__":
    main()
