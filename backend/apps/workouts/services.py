"""Training math: estimated 1-rep max, personal records, progress series and summaries.

PRs are computed on the fly from the stored sets instead of being stored, so
editing or deleting an old workout can never leave stale PR data behind.
"""
from collections import defaultdict
from decimal import Decimal

from django.db.models import Case, Count, F, FloatField, Max, Q, Sum, Value, When
from django.db.models.functions import Cast

from .models import WorkoutExercise, WorkoutSet


def e1rm(weight, reps):
    """Epley formula: estimated one-rep max = weight x (1 + reps / 30); a single is exact."""
    weight = float(weight)
    return weight if reps == 1 else weight * (1 + reps / 30)


# The same formula as a database expression, for aggregate queries.
E1RM_SQL = Case(
    When(reps=1, then=Cast("weight_kg", FloatField())),
    default=Cast("weight_kg", FloatField()) * (Value(1.0) + Cast("reps", FloatField()) / Value(30.0)),
    output_field=FloatField(),
)
VOLUME_SQL = Cast(F("weight_kg") * F("reps"), FloatField())


def _earlier_than(workout, prefix="workout_exercise__workout__"):
    """Q filter for this user's workouts that happened before `workout`."""
    return Q(**{f"{prefix}user_id": workout.user_id}) & (
        Q(**{f"{prefix}performed_on__lt": workout.performed_on})
        | Q(**{f"{prefix}performed_on": workout.performed_on, f"{prefix}created_at__lt": workout.created_at})
    )


def personal_records(workout):
    """Sets in `workout` that beat everything the user did before for that exercise.

    Returns {set_id: ["weight", "e1rm"]}. Only the best set per exercise and
    record type is flagged, and only if the exercise has earlier history (the
    first time you do an exercise isn't a "record").
    """
    sets = [s for we in workout.exercises.all() for s in we.sets.all()]
    if not sets:
        return {}
    exercise_ids = {we.exercise_id for we in workout.exercises.all()}
    previous = {
        row["workout_exercise__exercise_id"]: row
        for row in WorkoutSet.objects.filter(_earlier_than(workout), workout_exercise__exercise_id__in=exercise_ids)
        .values("workout_exercise__exercise_id")
        .annotate(max_weight=Max("weight_kg"), max_e1rm=Max(E1RM_SQL))
    }

    records = defaultdict(list)
    for we in workout.exercises.all():
        prev = previous.get(we.exercise_id)
        we_sets = list(we.sets.all())
        if prev is None or not we_sets:
            continue
        heaviest = max(we_sets, key=lambda s: (s.weight_kg, s.reps))
        if heaviest.weight_kg > prev["max_weight"]:
            records[heaviest.id].append("weight")
        strongest = max(we_sets, key=lambda s: e1rm(s.weight_kg, s.reps))
        if e1rm(strongest.weight_kg, strongest.reps) > (prev["max_e1rm"] or 0) + 1e-9:
            records[strongest.id].append("e1rm")
    return dict(records)


def workout_summary(workout, records=None):
    """Totals and per-exercise best sets, used for the stats card on posts."""
    if records is None:
        records = personal_records(workout)
    exercises = []
    total_sets = 0
    total_volume = Decimal(0)
    for we in workout.exercises.all():
        we_sets = list(we.sets.all())
        total_sets += len(we_sets)
        volume = sum((s.weight_kg * s.reps for s in we_sets), Decimal(0))
        total_volume += volume
        best = max(we_sets, key=lambda s: (s.weight_kg, s.reps)) if we_sets else None
        exercises.append(
            {
                "exercise_id": we.exercise_id,
                "name": we.exercise.name,
                "sets": len(we_sets),
                "best_set": {"weight_kg": float(best.weight_kg), "reps": best.reps} if best else None,
                "volume_kg": float(volume),
                "is_pr": any(s.id in records for s in we_sets),
            }
        )
    duration_min = None
    if workout.started_at and workout.finished_at and workout.finished_at > workout.started_at:
        duration_min = round((workout.finished_at - workout.started_at).total_seconds() / 60)
    return {
        "exercise_count": len(exercises),
        "set_count": total_sets,
        "volume_kg": float(total_volume),
        "duration_min": duration_min,
        "pr_count": sum(len(kinds) for kinds in records.values()),
        "exercises": exercises,
    }


def exercise_progress(user, exercise_id, since=None):
    """One point per training day: heaviest weight, best e1RM, total volume."""
    qs = WorkoutSet.objects.filter(workout_exercise__workout__user=user, workout_exercise__exercise_id=exercise_id)
    if since:
        qs = qs.filter(workout_exercise__workout__performed_on__gte=since)
    rows = (
        qs.values(date=F("workout_exercise__workout__performed_on"))
        .annotate(max_weight=Max("weight_kg"), best_e1rm=Max(E1RM_SQL), volume=Sum(VOLUME_SQL), sets=Count("id"))
        .order_by("date")
    )
    return [
        {
            "date": row["date"],
            "max_weight_kg": float(row["max_weight"]),
            "best_e1rm_kg": round(row["best_e1rm"], 2),
            "volume_kg": round(row["volume"], 1),
            "sets": row["sets"],
        }
        for row in rows
    ]


def last_session(user, exercise_id, before_workout=None):
    """Sets from the most recent time the user did this exercise (for 'previous' hints)."""
    qs = WorkoutExercise.objects.filter(workout__user=user, exercise_id=exercise_id)
    if before_workout is not None:
        qs = qs.exclude(workout=before_workout)
    we = qs.select_related("workout").prefetch_related("sets").order_by("-workout__performed_on", "-workout__created_at").first()
    if we is None:
        return None
    return {
        "workout_id": we.workout_id,
        "performed_on": we.workout.performed_on,
        "sets": [{"weight_kg": float(s.weight_kg), "reps": s.reps} for s in we.sets.all()],
    }
