"""Prediction and model-publication regression tests using an isolated test DB."""

from contextlib import redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Experiment, ExperimentResult, ModelSettings, ModelVersion


ROOT = Path(__file__).resolve().parents[2]


class VersionPredictionTests(APITestCase):
    def setUp(self):
        self.experiment = Experiment.objects.create(name="Prediction test fixture")

    def make_version(self, model_name="logistic_regression", copy_file=True):
        version = ModelVersion(experiment=self.experiment, model_name=model_name)
        version.artifact = f"{version.id}.joblib"
        version.save()
        if copy_file:
            destination = ROOT / "models" / "versions" / version.artifact
            destination.parent.mkdir(parents=True, exist_ok=True)
            self.assertFalse(destination.exists())
            self.addCleanup(destination.unlink, missing_ok=True)
            shutil.copy2(ROOT / "models" / f"{model_name}.joblib", destination)
        return version

    def test_default_prediction_works(self):
        response = self.client.post(
            "/api/predict/", {"review": "This was an excellent movie with great acting."},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["prediction"], "Positive")
        self.assertIsNone(response.data["version_id"])
        self.assertGreaterEqual(response.data["confidence"], 0.5)
        self.assertLessEqual(response.data["confidence"], 1.0)

    def test_each_registered_model_can_predict(self):
        for model_name in ["naive_bayes", "logistic_regression"]:
            with self.subTest(model=model_name):
                version = self.make_version(model_name)
                response = self.client.post("/api/predict/", {
                    "review": "The movie was boring, confusing, and poorly acted.",
                    "version_id": str(version.id),
                }, format="json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data["prediction"], "Negative")
                self.assertEqual(response.data["model_name"], model_name)
                self.assertEqual(response.data["version_id"], str(version.id))

    def test_invalid_reviews_are_rejected(self):
        for payload in [{}, {"review": ""}, {"review": "   "}, {"review": None},
                        {"review": 123}, {"review": "x" * 10001}, ["not a JSON object"]]:
            with self.subTest(payload_type=type(payload).__name__):
                response = self.client.post("/api/predict/", payload, format="json")
                self.assertEqual(response.status_code, 400)

    def test_malformed_version_id_is_rejected(self):
        response = self.client.post("/api/predict/", {
            "review": "Great movie", "version_id": "not-a-uuid",
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_unknown_version_returns_not_found(self):
        response = self.client.post("/api/predict/", {
            "review": "Great movie", "version_id": str(uuid4()),
        }, format="json")
        self.assertEqual(response.status_code, 404)

    def test_missing_model_file_returns_service_unavailable(self):
        version = self.make_version(copy_file=False)
        with self.assertLogs(level="ERROR"):
            response = self.client.post("/api/predict/", {
                "review": "Great movie", "version_id": str(version.id),
            }, format="json")
        self.assertEqual(response.status_code, 503)

    def test_version_registry_is_public_and_hides_artifact_paths(self):
        version = self.make_version(copy_file=False)
        response = self.client.get("/api/model-versions/")
        self.assertEqual(response.status_code, 200)
        item = next(row for row in response.data if row["id"] == str(version.id))
        self.assertEqual(item["model_name"], version.model_name)
        self.assertNotIn("artifact", item)

    def test_version_registry_is_read_only(self):
        response = self.client.post("/api/model-versions/", {
            "model_name": "naive_bayes",
        }, format="json")
        self.assertEqual(response.status_code, 405)

    def test_prediction_requires_post(self):
        self.assertEqual(self.client.get("/api/predict/").status_code, 405)


class PublishedModelTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory(prefix="mlflowpro-publish-test-")
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        spec = importlib.util.spec_from_file_location("publication_under_test", ROOT / "publish_model.py")
        self.publisher = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.publisher)
        self.publisher.ROOT = self.root
        self.experiment = Experiment.objects.create(name="Publication test fixture", dataset="Test metadata")
        self.version = ModelVersion(
            experiment=self.experiment, model_name="logistic_regression",
            parameters={"max_features": 50000, "ngram_range": [1, 2], "classifier": {"C": 1.0}},
            metrics={"accuracy": 0.9, "f1_score": 0.89},
        )
        self.version.artifact = f"{self.version.id}.joblib"
        self.snapshot = self.root / "models" / "versions" / self.version.artifact
        self.snapshot.parent.mkdir(parents=True)
        shutil.copy2(ROOT / "models" / "logistic_regression.joblib", self.snapshot)
        self.version.provenance = {
            "artifact_sha256": hashlib.sha256(self.snapshot.read_bytes()).hexdigest(),
            "evaluation_status": "Unit-test fixture; these are not reported project scores",
        }
        self.version.save()
        ExperimentResult.objects.create(
            experiment=self.experiment, model_name="logistic_regression",
            accuracy=0.9, f1_score=0.89, training_time=1.25,
        )
        with redirect_stdout(io.StringIO()):
            self.publisher.export_version(self.version.id)

    def test_restore_preserves_data_and_repairs_missing_files_without_duplicates(self):
        identifier = self.version.id
        self.version.delete()
        self.experiment.delete()
        self.snapshot.unlink()
        with redirect_stdout(io.StringIO()):
            self.publisher.restore_versions()
        restored = ModelVersion.objects.get(pk=identifier)
        self.assertEqual(restored.metrics, {"accuracy": 0.9, "f1_score": 0.89})
        self.assertEqual(restored.experiment.results.get().training_time, 1.25)
        self.assertTrue(self.snapshot.is_file())
        self.snapshot.unlink()
        with redirect_stdout(io.StringIO()):
            self.publisher.restore_versions()
        self.assertTrue(self.snapshot.is_file())
        self.assertEqual(ModelVersion.objects.count(), 1)
        self.assertEqual(ExperimentResult.objects.count(), 1)
        self.assertEqual(ModelSettings.objects.count(), 1)

    def test_corrupted_published_model_is_rejected(self):
        package = self.root / "published_models" / str(self.version.id) / "model.joblib"
        package.write_bytes(b"This is not the registered model.")
        with self.assertRaisesRegex(ValueError, "hash check"):
            self.publisher.restore_versions()
        self.assertEqual(ModelVersion.objects.count(), 1)
        self.assertEqual(ExperimentResult.objects.count(), 1)
