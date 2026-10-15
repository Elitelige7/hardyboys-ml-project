from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from experiments.views import (
    ExperimentViewSet,
    ModelSettingsViewSet,
    ExperimentResultViewSet,
)

router = DefaultRouter()
router.register("experiments", ExperimentViewSet)
router.register("model-settings", ModelSettingsViewSet)
router.register("experiment-results", ExperimentResultViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
]