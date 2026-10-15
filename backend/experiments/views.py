from rest_framework import viewsets
from .models import Experiment, ModelSettings, ExperimentResult
from .serializers import (
    ExperimentSerializer,
    ModelSettingsSerializer,
    ExperimentResultSerializer,
)


class ExperimentViewSet(viewsets.ModelViewSet):
    queryset = Experiment.objects.all().order_by("-created_at")
    serializer_class = ExperimentSerializer


class ModelSettingsViewSet(viewsets.ModelViewSet):
    queryset = ModelSettings.objects.all()
    serializer_class = ModelSettingsSerializer


class ExperimentResultViewSet(viewsets.ModelViewSet):
    queryset = ExperimentResult.objects.all().order_by("-created_at")
    serializer_class = ExperimentResultSerializer