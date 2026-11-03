from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class ExerciseQuerySet(models.QuerySet):
    def visible_to(self, user):
        """The global catalogue plus the user's own custom exercises."""
        return self.filter(models.Q(owner__isnull=True) | models.Q(owner=user))


class Exercise(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, blank=True)  # catalogue id; empty for custom exercises
    category = models.CharField(max_length=40, blank=True)
    equipment = models.CharField(max_length=40, blank=True)
    level = models.CharField(max_length=20, blank=True)
    primary_muscles = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    secondary_muscles = ArrayField(models.CharField(max_length=30), default=list, blank=True)
    instructions = models.TextField(blank=True)
    # NULL = part of the shared catalogue; otherwise a private custom exercise.
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="custom_exercises"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = ExerciseQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        indexes = [
            # Trigram index: fast fuzzy search ("bench pres", "squats") with pg_trgm.
            GinIndex(fields=["name"], name="exercise_name_trgm", opclasses=["gin_trgm_ops"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slug"], condition=models.Q(owner__isnull=True), name="exercise_catalogue_slug_unique"
            ),
            models.UniqueConstraint(Lower("name"), "owner", name="exercise_custom_name_unique"),
        ]

    def __str__(self):
        return self.name


class Workout(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workouts")
    title = models.CharField(max_length=100, blank=True)
    performed_on = models.DateField()
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-performed_on", "-created_at"]
        indexes = [models.Index(fields=["user", "performed_on"], name="workout_user_date_idx")]

    def __str__(self):
        return f"{self.user} {self.performed_on} {self.title}"


class WorkoutExercise(models.Model):
    workout = models.ForeignKey(Workout, on_delete=models.CASCADE, related_name="exercises")
    # RESTRICT (not PROTECT): an exercise in use can't be deleted on its own, but
    # deleting a user may remove their custom exercises together with their workouts.
    exercise = models.ForeignKey(Exercise, on_delete=models.RESTRICT, related_name="+")
    order = models.PositiveSmallIntegerField()
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["order"]


class WorkoutSet(models.Model):
    workout_exercise = models.ForeignKey(WorkoutExercise, on_delete=models.CASCADE, related_name="sets")
    order = models.PositiveSmallIntegerField()
    # Always stored in kilograms; the frontend converts for users who prefer pounds.
    weight_kg = models.DecimalField(
        max_digits=7, decimal_places=3, validators=[MinValueValidator(0), MaxValueValidator(1500)]
    )
    reps = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(1000)])

    class Meta:
        ordering = ["order"]


class WorkoutTemplate(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="templates")
    name = models.CharField(max_length=100)
    notes = models.TextField(max_length=2000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class TemplateExercise(models.Model):
    template = models.ForeignKey(WorkoutTemplate, on_delete=models.CASCADE, related_name="exercises")
    exercise = models.ForeignKey(Exercise, on_delete=models.RESTRICT, related_name="+")
    order = models.PositiveSmallIntegerField()
    target_sets = models.PositiveSmallIntegerField(default=3, validators=[MinValueValidator(1), MaxValueValidator(20)])
    target_reps = models.PositiveSmallIntegerField(default=10, validators=[MinValueValidator(1), MaxValueValidator(100)])

    class Meta:
        ordering = ["order"]
