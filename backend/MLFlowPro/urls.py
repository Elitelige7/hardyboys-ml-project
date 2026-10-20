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

# MLFlowPro: AI experiment suggestions
from experiments.ai_suggestions import suggest_experiment

# MLFlowPro: GitHub OAuth routes
from experiments.github_auth import github_login, github_callback, team_logout

urlpatterns = [
    path("accounts/github/login/", github_login),
    path("accounts/github/login/callback/", github_callback),
    path("team/logout/", team_logout, name="team-logout"),
    path("accounts/", include("allauth.urls")),

    path("api/ai-suggestions/", suggest_experiment, name="ai-suggestions"),
    path("admin/", admin.site.urls),
    path("api/predict/", predict_review, name="predict-review"),
    path("api/", include(router.urls)),
    path("api-auth/", include("rest_framework.urls")),
    path("", TemplateView.as_view(template_name="index.html"), name="dashboard"),
]