from pathlib import Path

from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.permissions import AllowAny
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
    permission_classes = [IsAuthenticatedOrReadOnly]

    from pathlib import Path
import joblib
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status


MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "logistic_regression.joblib"
)
model = joblib.load(MODEL_PATH)


@api_view(["POST"])
@permission_classes([AllowAny])
def predict_review(request):
    review = request.data.get("review", "").strip()

    if not review:
        return Response(
            {"error": "Please enter a movie review."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    prediction = str(model.predict([review])[0]).capitalize()

    confidence = None
    if hasattr(model, "predict_proba"):
        probabilities = model.predict_proba([review])[0]
        confidence = round(float(max(probabilities)), 4)

    return Response({
        "prediction": prediction,
        "confidence": confidence,
    })