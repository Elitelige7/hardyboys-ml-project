"""AI endpoint checks use simulated provider responses, without spending API credit."""

import json
import os
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import httpx
from openai import OpenAI
from django.core.cache import cache
from rest_framework.test import APITestCase

from .models import Experiment, ModelVersion


class AISuggestionTests(APITestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-key-no-network", "OPENAI_MODEL": "gpt-5.4-mini",
            "MLFLOWPRO_AI_ACCESS_CODE": "test-team-access-code",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        cache.delete("mlflowpro-ai-suggestions")
        self.addCleanup(cache.delete, "mlflowpro-ai-suggestions")
        self.factory = patch("experiments.ai_suggestions.OpenAI")
        self.provider = self.factory.start()
        self.addCleanup(self.factory.stop)
        self.responses = self.provider.return_value.__enter__.return_value.responses
        self.responses.create.return_value = SimpleNamespace(
            status="completed", output_text="Try C=2. Evaluate with training-only cross-validation.",
        )

    def post(self, payload=None, code="test-team-access-code"):
        return self.client.post("/api/ai-suggestions/", payload if payload is not None else {
            "goal": "Suggest a Logistic Regression experiment.",
        }, format="json", HTTP_X_MLFLOWPRO_ACCESS_CODE=code)

    def test_valid_request_returns_draft_without_training_or_database_writes(self):
        before = ModelVersion.objects.count()
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertIn("Try C=2", response.data["suggestion"])
        self.assertEqual(ModelVersion.objects.count(), before)
        arguments = self.responses.create.call_args.kwargs
        self.assertFalse(arguments["store"])
        self.assertEqual(arguments["max_output_tokens"], 1400)
        self.assertNotIn("tools", arguments)

    def test_missing_configuration_does_not_call_provider(self):
        for name in ["OPENAI_API_KEY", "MLFLOWPRO_AI_ACCESS_CODE"]:
            with self.subTest(name=name), patch.dict(os.environ, {name: ""}):
                self.assertEqual(self.post().status_code, 503)
        self.provider.assert_not_called()

    def test_missing_or_wrong_access_code_is_rejected_before_provider_call(self):
        for code in ["", "wrong-code"]:
            with self.subTest(code=code):
                self.assertEqual(self.post(code=code).status_code, 403)
        self.provider.assert_not_called()

    def test_invalid_goals_are_rejected(self):
        for payload in [{}, {"goal": " "}, {"goal": 5}, {"goal": "x" * 1201}, ["invalid"]]:
            with self.subTest(payload_type=type(payload).__name__):
                self.assertEqual(self.post(payload).status_code, 400)
        self.provider.assert_not_called()

    def test_unknown_or_malformed_version_is_rejected(self):
        for identifier, status in [("bad-id", 400), (str(uuid4()), 404)]:
            with self.subTest(identifier=identifier):
                response = self.post({"goal": "Suggest settings.", "version_id": identifier})
                self.assertEqual(response.status_code, status)
        self.provider.assert_not_called()

    def test_context_uses_selected_settings_and_omits_test_scores_and_file_paths(self):
        experiment = Experiment.objects.create(name="AI context fixture")
        version = ModelVersion.objects.create(
            experiment=experiment, model_name="logistic_regression", artifact="private-model.joblib",
            parameters={"max_features": 50000, "ngram_range": [1, 2], "classifier": {"C": 2.0},
                        "optimization": {"best_cv_f1": 0.8}},
            metrics={"accuracy": 0.9, "f1_score": 0.89},
            provenance={"dataset_file": "private-file.csv"},
        )
        response = self.post({"goal": "Suggest settings.", "version_id": str(version.id)})
        self.assertEqual(response.status_code, 200)
        context = json.loads(self.responses.create.call_args.kwargs["input"])["existing_training_settings"]
        self.assertEqual(context, [{"model_name": "logistic_regression", "parameters": {
            "max_features": 50000, "ngram_range": [1, 2], "C": 2.0,
        }, "previous_training_cv_macro_f1": 0.8}])

    def test_provider_network_failure_is_reported_without_secrets(self):
        from openai import APIConnectionError
        self.responses.create.side_effect = APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        with self.assertLogs("experiments.ai_suggestions", level="WARNING"):
            response = self.post()
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("test-key", json.dumps(response.data))

    def test_empty_or_incomplete_provider_output_is_rejected(self):
        for status, text in [("completed", ""), ("incomplete", "Partial code")]:
            with self.subTest(status=status):
                self.responses.create.return_value = SimpleNamespace(status=status, output_text=text)
                self.assertEqual(self.post().status_code, 502)

    def test_rate_limit_prevents_excess_provider_calls(self):
        for _ in range(5):
            self.assertEqual(self.post().status_code, 200)
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.assertEqual(self.responses.create.call_count, 5)

    def test_official_sdk_payload_and_text_extraction_using_mock_http(self):
        requests = []

        def respond(request):
            self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={
                "id": "resp_test", "object": "response", "created_at": 1, "status": "completed",
                "model": "gpt-5.4-mini", "output": [{
                    "id": "msg_test", "type": "message", "role": "assistant", "status": "completed",
                    "content": [{"type": "output_text", "text": "Suggested pipeline draft.", "annotations": []}],
                }],
            })

        sdk = OpenAI(api_key="test-key-no-network", http_client=httpx.Client(transport=httpx.MockTransport(respond)))
        self.provider.return_value = sdk
        response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["suggestion"], "Suggested pipeline draft.")
        self.assertEqual(requests[0]["model"], "gpt-5.4-mini")
        self.assertFalse(requests[0]["store"])

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get("/api/ai-suggestions/").status_code, 405)
