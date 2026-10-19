from django.db import models
import uuid


class Experiment(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    dataset = models.CharField(max_length=200, default="Movie Reviews")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ModelSettings(models.Model):
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name="model_settings"
    )
    model_name = models.CharField(max_length=100)
    max_features = models.IntegerField(default=5000)
    ngram_min = models.IntegerField(default=1)
    ngram_max = models.IntegerField(default=2)
    parameters = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"{self.experiment.name} - {self.model_name}"


class ExperimentResult(models.Model):
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.CASCADE,
        related_name="results"
    )
    model_name = models.CharField(max_length=100)
    accuracy = models.FloatField()
    f1_score = models.FloatField()
    training_time = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.model_name} - {self.experiment.name}"

class ModelVersion(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )
    experiment = models.ForeignKey(
        Experiment,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    model_name = models.CharField(max_length=100)
    parameters = models.JSONField(default=dict)
    metrics = models.JSONField(default=dict)
    provenance = models.JSONField(default=dict)
    artifact = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.model_name} - {str(self.id)[:8]}"

# MLFlowPro: persistent shared experiment notes
class CollaborationNote(models.Model):
    key = models.CharField(max_length=40, primary_key=True, default="team")
    body = models.TextField(blank=True, default="")
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Shared experiment notes"
