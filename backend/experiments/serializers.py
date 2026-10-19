from .models import ModelVersion
from rest_framework import serializers
from .models import Experiment, ModelSettings, ExperimentResult


class ExperimentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experiment
        fields = "__all__"


class ModelSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelSettings
        fields = "__all__"


class ExperimentResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExperimentResult
        fields = "__all__"

class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = [
            "id",
            "experiment",
            "model_name",
            "parameters",
            "metrics",
            "provenance",
            "created_at",
        ]