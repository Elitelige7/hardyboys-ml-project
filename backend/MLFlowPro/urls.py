from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.views.generic import TemplateView
from experiments.views import ModelVersionViewSet

from experiments.views import (
    ExperimentViewSet,
    ModelSettingsViewSet,
    ExperimentResultViewSet,
    predict_review,
)

router = DefaultRouter()
router.register("experiments", ExperimentViewSet)
router.register("model-settings", ModelSettingsViewSet)
router.register("experiment-results", ExperimentResultViewSet)
router.register("model-versions", ModelVersionViewSet, basename="model-version",)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/predict/", predict_review, name="predict-review"),
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("", TemplateView.as_view(template_name="index.html"), name="dashboard"),
]