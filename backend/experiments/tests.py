from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from .models import Experiment, ModelSettings, ExperimentResult


class ExperimentAPITests(APITestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="testuser",
            password="TestPassword123!"
        )

        self.client.force_authenticate(user=self.user)

        self.experiment = Experiment.objects.create(
            name="Test Experiment",
            description="Testing the MLFlowPro API",
            dataset="Test Dataset",
        )

    def test_create_experiment(self):
        url = reverse("experiment-list")

        data = {
            "name": "New Experiment",
            "description": "Created through the API",
            "dataset": "IMDb Movie Reviews",
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Experiment.objects.filter(name="New Experiment").exists()
        )

    def test_list_experiments(self):
        url = reverse("experiment-list")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            any(
                item["name"] == "Test Experiment"
                for item in response.data
            )
        )

    def test_create_model_settings(self):
        url = reverse("modelsettings-list")

        data = {
            "experiment": self.experiment.id,
            "model_name": "Logistic Regression",
            "max_features": 5000,
            "ngram_min": 1,
            "ngram_max": 2,
            "parameters": {},
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ModelSettings.objects.filter(
                experiment=self.experiment,
                model_name="Logistic Regression",
            ).exists()
        )

    def test_create_experiment_result(self):
        url = reverse("experimentresult-list")

        data = {
            "experiment": self.experiment.id,
            "model_name": "Logistic Regression",
            "accuracy": 0.90,
            "f1_score": 0.89,
            "training_time": 2.5,
        }

        response = self.client.post(url, data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ExperimentResult.objects.filter(
                experiment=self.experiment,
                model_name="Logistic Regression",
            ).exists()
        )

    def test_api_requires_authentication(self):
        anonymous_client = APIClient()

        response = anonymous_client.get(
            reverse("experiment-list")
        )

        self.assertIn(response.status_code, [401, 403])