from django.db import transaction
from rest_framework import serializers

from .models import Exercise, TemplateExercise, Workout, WorkoutExercise, WorkoutSet, WorkoutTemplate
from .services import personal_records, workout_summary

MAX_EXERCISES = 30
MAX_SETS = 50


class ExerciseSerializer(serializers.ModelSerializer):
    is_custom = serializers.SerializerMethodField()

    class Meta:
        model = Exercise
        fields = [
            "id",
            "name",
            "category",
            "equipment",
            "level",
            "primary_muscles",
            "secondary_muscles",
            "instructions",
            "is_custom",
        ]
        read_only_fields = ["id", "level", "is_custom"]

    def get_is_custom(self, exercise):
        return exercise.owner_id is not None

    def validate_name(self, value):
        value = value.strip()
        user = self.context["request"].user
        if Exercise.objects.filter(owner=user, name__iexact=value).exists():
            raise serializers.ValidationError("You already have a custom exercise with this name.")
        return value


class ExerciseBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exercise
        fields = ["id", "name", "category", "equipment", "primary_muscles"]


class SetSerializer(serializers.ModelSerializer):
    weight_kg = serializers.DecimalField(max_digits=7, decimal_places=3, min_value=0, max_value=1500)
    reps = serializers.IntegerField(min_value=1, max_value=1000)

    class Meta:
        model = WorkoutSet
        fields = ["id", "weight_kg", "reps"]
        read_only_fields = ["id"]


class WorkoutExerciseSerializer(serializers.ModelSerializer):
    exercise = ExerciseBriefSerializer(read_only=True)
    exercise_id = serializers.IntegerField(write_only=True)
    sets = SetSerializer(many=True)

    class Meta:
        model = WorkoutExercise
        fields = ["id", "exercise", "exercise_id", "notes", "sets"]
        read_only_fields = ["id"]

    def validate_sets(self, value):
        if not 1 <= len(value) <= MAX_SETS:
            raise serializers.ValidationError(f"Log between 1 and {MAX_SETS} sets.")
        return value


def validate_exercise_ids(user, entries):
    """Every exercise must be from the catalogue or the user's own custom ones."""
    ids = {entry["exercise_id"] for entry in entries}
    visible = set(Exercise.objects.visible_to(user).filter(id__in=ids).values_list("id", flat=True))
    missing = ids - visible
    if missing:
        raise serializers.ValidationError(f"Unknown exercise id(s): {sorted(missing)}")


class WorkoutSerializer(serializers.ModelSerializer):
    exercises = WorkoutExerciseSerializer(many=True)
    summary = serializers.SerializerMethodField()
    records = serializers.SerializerMethodField()
    post_id = serializers.SerializerMethodField()

    class Meta:
        model = Workout
        fields = [
            "id",
            "title",
            "performed_on",
            "started_at",
            "finished_at",
            "notes",
            "exercises",
            "summary",
            "records",
            "post_id",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def _records(self, workout):
        # Computed once per workout and shared by summary + records fields.
        cache = self.context.setdefault("_records", {})
        if workout.pk not in cache:
            cache[workout.pk] = personal_records(workout)
        return cache[workout.pk]

    def get_records(self, workout):
        return {str(set_id): kinds for set_id, kinds in self._records(workout).items()}

    def get_summary(self, workout):
        return workout_summary(workout, self._records(workout))

    def get_post_id(self, workout):
        post = getattr(workout, "post", None)
        return post.id if post else None

    def validate_exercises(self, value):
        if not 1 <= len(value) <= MAX_EXERCISES:
            raise serializers.ValidationError(f"Add between 1 and {MAX_EXERCISES} exercises.")
        validate_exercise_ids(self.context["request"].user, value)
        return value

    def validate(self, attrs):
        started, finished = attrs.get("started_at"), attrs.get("finished_at")
        if started and finished and finished < started:
            raise serializers.ValidationError({"finished_at": "Must be after the start time."})
        return attrs

    def _write_exercises(self, workout, exercises):
        for position, entry in enumerate(exercises):
            we = WorkoutExercise.objects.create(
                workout=workout, exercise_id=entry["exercise_id"], order=position, notes=entry.get("notes", "")
            )
            WorkoutSet.objects.bulk_create(
                WorkoutSet(workout_exercise=we, order=i, weight_kg=s["weight_kg"], reps=s["reps"])
                for i, s in enumerate(entry["sets"])
            )

    @transaction.atomic
    def create(self, validated_data):
        exercises = validated_data.pop("exercises")
        workout = Workout.objects.create(user=self.context["request"].user, **validated_data)
        self._write_exercises(workout, exercises)
        return workout

    @transaction.atomic
    def update(self, workout, validated_data):
        exercises = validated_data.pop("exercises", None)
        for field, value in validated_data.items():
            setattr(workout, field, value)
        workout.save()
        if exercises is not None:
            # Simplest correct approach for an edit form: replace all rows.
            workout.exercises.all().delete()
            self._write_exercises(workout, exercises)
        return workout


class TemplateExerciseSerializer(serializers.ModelSerializer):
    exercise = ExerciseBriefSerializer(read_only=True)
    exercise_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = TemplateExercise
        fields = ["id", "exercise", "exercise_id", "target_sets", "target_reps"]
        read_only_fields = ["id"]


class TemplateSerializer(serializers.ModelSerializer):
    exercises = TemplateExerciseSerializer(many=True)

    class Meta:
        model = WorkoutTemplate
        fields = ["id", "name", "notes", "exercises", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_exercises(self, value):
        if not 1 <= len(value) <= MAX_EXERCISES:
            raise serializers.ValidationError(f"Add between 1 and {MAX_EXERCISES} exercises.")
        validate_exercise_ids(self.context["request"].user, value)
        return value

    def _write_exercises(self, template, exercises):
        TemplateExercise.objects.bulk_create(
            TemplateExercise(
                template=template,
                exercise_id=entry["exercise_id"],
                order=position,
                target_sets=entry.get("target_sets", 3),
                target_reps=entry.get("target_reps", 10),
            )
            for position, entry in enumerate(exercises)
        )

    @transaction.atomic
    def create(self, validated_data):
        exercises = validated_data.pop("exercises")
        template = WorkoutTemplate.objects.create(user=self.context["request"].user, **validated_data)
        self._write_exercises(template, exercises)
        return template

    @transaction.atomic
    def update(self, template, validated_data):
        exercises = validated_data.pop("exercises", None)
        for field, value in validated_data.items():
            setattr(template, field, value)
        template.save()
        if exercises is not None:
            template.exercises.all().delete()
            self._write_exercises(template, exercises)
        return template
