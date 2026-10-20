from pathlib import Path

import logging
from uuid import UUID
from .models import ModelVersion
from .models import ModelVersion
from .serializers import ModelVersionSerializer
from rest_framework.permissions import AllowAny
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
    if not isinstance(request.data, dict):
        return Response({"error": "Send a JSON object."}, status=400)

    review = request.data.get("review")
    if not isinstance(review, str) or not review.strip():
        return Response(
            {"error": "Please enter a movie review."},
            status=400,
        )
    if len(review) > 10000:
        return Response(
            {"error": "Review must be 10,000 characters or fewer."},
            status=400,
        )
    review = review.strip()

    pipeline = model
    version = None
    version_id = request.data.get("version_id")

    if version_id:
        try:
            parsed_id = UUID(str(version_id))
        except (ValueError, TypeError):
            return Response({"error": "Invalid version ID."}, status=400)

        try:
            version = ModelVersion.objects.get(pk=parsed_id)
        except ModelVersion.DoesNotExist:
            return Response(
                {"error": "Model version was not found."},
                status=404,
            )

    try:
        if version is not None:
            saved_path = (
                Path(__file__).resolve().parents[2]
                / "models" / "versions" / version.artifact
            )
            pipeline = joblib.load(saved_path)

        prediction = str(pipeline.predict([review])[0]).capitalize()
        confidence = round(
            float(max(pipeline.predict_proba([review])[0])),
            4,
        )
    except Exception:
        logging.exception("Movie review prediction failed")
        return Response(
            {"error": "Model file is unavailable or incompatible."},
            status=503,
        )

    return Response({
        "prediction": prediction,
        "confidence": confidence,
        "model_name": (
            version.model_name if version else "logistic_regression"
        ),
        "version_id": str(version.id) if version else None,
    })


class ModelVersionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ModelVersion.objects.all().order_by("-created_at")
    serializer_class = ModelVersionSerializer
    permission_classes = [AllowAny]