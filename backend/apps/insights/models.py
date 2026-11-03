from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


def _measure(max_value):
    return models.DecimalField(
        max_digits=5,
        decimal_places=1,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(max_value)],
    )


class BodyMetric(models.Model):
    """One check-in per day: bodyweight and optional measurements (stored in kg / cm)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="body_metrics")
    measured_on = models.DateField()
    bodyweight_kg = models.DecimalField(
        max_digits=6, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(20), MaxValueValidator(400)]
    )
    body_fat_pct = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True, validators=[MinValueValidator(2), MaxValueValidator(75)]
    )
    waist_cm = _measure(300)
    chest_cm = _measure(300)
    arm_cm = _measure(150)
    thigh_cm = _measure(200)
    hips_cm = _measure(300)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-measured_on"]
        constraints = [models.UniqueConstraint(fields=["user", "measured_on"], name="body_metric_one_per_day")]


class Challenge(models.Model):
    """A head-to-head challenge between two friends over a date range."""

    class Metric(models.TextChoices):
        TOTAL_VOLUME = "total_volume", "Total volume"
        WORKOUT_COUNT = "workout_count", "Number of workouts"
        EXERCISE_VOLUME = "exercise_volume", "Volume on one exercise"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        DECLINED = "declined", "Declined"
        FINISHED = "finished", "Finished"

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenges_created")
    opponent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="challenges_received")
    metric = models.CharField(max_length=20, choices=Metric.choices)
    exercise = models.ForeignKey("workouts.Exercise", null=True, blank=True, on_delete=models.RESTRICT, related_name="+")
    starts_on = models.DateField()
    ends_on = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    winner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(ends_on__gte=models.F("starts_on")), name="challenge_dates_ordered"),
            models.CheckConstraint(condition=~models.Q(creator=models.F("opponent")), name="challenge_not_self"),
        ]
