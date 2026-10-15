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