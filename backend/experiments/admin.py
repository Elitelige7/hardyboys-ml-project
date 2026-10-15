from django.contrib import admin
from .models import Experiment, ModelSettings, ExperimentResult


@admin.register(Experiment)
class ExperimentAdmin(admin.ModelAdmin):
    list_display = ("name", "dataset", "created_at")
    search_fields = ("name", "dataset")


@admin.register(ModelSettings)
class ModelSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "experiment",
        "model_name",
        "max_features",
        "ngram_min",
        "ngram_max",
    )


@admin.register(ExperimentResult)
class ExperimentResultAdmin(admin.ModelAdmin):
    list_display = (
        "experiment",
        "model_name",
        "accuracy",
        "f1_score",
        "training_time",
        "created_at",
    )