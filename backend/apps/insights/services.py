"""Premium analytics: aggregate queries over the sets a user has logged."""
from collections import Counter, defaultdict
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import Count, F, Max, Sum
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

from apps.accounts.models import User
from apps.social.models import Notification
from apps.social.services import notify
from apps.social.visibility import friend_ids
from apps.workouts.models import Exercise, Workout, WorkoutSet
from apps.workouts.services import E1RM_SQL, VOLUME_SQL, personal_records

from .models import Challenge


def user_sets(user, start=None, end=None):
    qs = WorkoutSet.objects.filter(workout_exercise__workout__user=user)
    if start:
        qs = qs.filter(workout_exercise__workout__performed_on__gte=start)
    if end:
        qs = qs.filter(workout_exercise__workout__performed_on__lte=end)
    return qs


def muscle_volume(user, weeks=12):
    """Weekly volume (kg x reps) and set count per primary muscle group."""
    today = date.today()
    start = today - timedelta(days=today.weekday()) - timedelta(weeks=weeks - 1)
    rows = (
        user_sets(user, start=start)
        .annotate(week=TruncWeek("workout_exercise__workout__performed_on"))
        .values("week", "workout_exercise__exercise_id")
        .annotate(volume=Sum(VOLUME_SQL), sets=Count("id"))
    )
    rows = list(rows)
    muscles_of = dict(
        Exercise.objects.filter(id__in={r["workout_exercise__exercise_id"] for r in rows}).values_list("id", "primary_muscles")
    )
    week_keys = [(start + timedelta(weeks=i)).isoformat() for i in range(weeks)]
    position = {key: i for i, key in enumerate(week_keys)}
    volume = defaultdict(lambda: [0.0] * weeks)
    sets = defaultdict(lambda: [0] * weeks)
    for row in rows:
        index = position.get(row["week"].isoformat())  # TruncWeek on a DateField gives the Monday
        if index is None:
            continue
        for muscle in muscles_of.get(row["workout_exercise__exercise_id"]) or ["other"]:
            volume[muscle][index] += round(row["volume"] or 0, 1)
            sets[muscle][index] += row["sets"]
    return {"weeks": week_keys, "volume_kg": dict(volume), "sets": dict(sets)}


def heatmap(user, year):
    """Workouts and volume per day for a GitHub-style calendar heatmap."""
    days = {}
    for row in Workout.objects.filter(user=user, performed_on__year=year).values("performed_on").annotate(n=Count("id")):
        days[row["performed_on"].isoformat()] = {"workouts": row["n"], "volume_kg": 0}
    volumes = (
        user_sets(user, start=date(year, 1, 1), end=date(year, 12, 31))
        .values(day=F("workout_exercise__workout__performed_on"))
        .annotate(volume=Sum(VOLUME_SQL))
    )
    for row in volumes:
        days.setdefault(row["day"].isoformat(), {"workouts": 0, "volume_kg": 0})["volume_kg"] = round(row["volume"] or 0, 1)
    return {"year": year, "days": days}


def e1rm_trends(user, top=5):
    """Monthly best estimated 1RM for the user's most-trained exercises over the last year."""
    since = date.today() - timedelta(days=365)
    favourites = (
        user_sets(user, start=since)
        .values("workout_exercise__exercise_id", "workout_exercise__exercise__name")
        .annotate(sessions=Count("workout_exercise__workout", distinct=True))
        .order_by("-sessions")[:top]
    )
    result = []
    for fav in favourites:
        points = (
            user_sets(user, start=since)
            .filter(workout_exercise__exercise_id=fav["workout_exercise__exercise_id"])
            .annotate(month=TruncMonth("workout_exercise__workout__performed_on"))
            .values("month")
            .annotate(best=Max(E1RM_SQL))
            .order_by("month")
        )
        result.append(
            {
                "exercise_id": fav["workout_exercise__exercise_id"],
                "name": fav["workout_exercise__exercise__name"],
                "points": [{"month": p["month"].strftime("%Y-%m"), "best_e1rm_kg": round(p["best"], 1)} for p in points],
            }
        )
    return result


def relative_strength(user, bodyweight_kg):
    """Best e1RM on the top lifts as a multiple of bodyweight (e.g. bench 1.2 x BW)."""
    if not bodyweight_kg:
        return []
    rows = (
        user_sets(user, start=date.today() - timedelta(days=365))
        .values("workout_exercise__exercise__name")
        .annotate(best=Max(E1RM_SQL), sets=Count("id"))
        .order_by("-sets")[:6]
    )
    return [
        {
            "name": r["workout_exercise__exercise__name"],
            "best_e1rm_kg": round(r["best"], 1),
            "ratio": round(r["best"] / float(bodyweight_kg), 2),
        }
        for r in rows
    ]


# --- Recap -------------------------------------------------------------------------------

def period_bounds(month=None, year=None):
    if month:
        start = date.fromisoformat(f"{month}-01")
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        label = start.strftime("%B %Y")
        return start, end, label, month
    start, end = date(int(year), 1, 1), date(int(year), 12, 31)
    return start, end, f"{year} in review", str(year)


def _longest_weekly_streak(dates):
    weeks = sorted({d.isocalendar()[:2] for d in dates})
    best = run = 0
    previous = None
    for year, week in weeks:
        monday = date.fromisocalendar(year, week, 1)
        run = run + 1 if previous and monday - previous == timedelta(weeks=1) else 1
        best = max(best, run)
        previous = monday
    return best


def recap(user, start, end):
    workouts = list(
        Workout.objects.filter(user=user, performed_on__range=(start, end)).prefetch_related(
            "exercises__exercise", "exercises__sets"
        )
    )
    sets = user_sets(user, start, end)
    totals = sets.aggregate(volume=Sum(VOLUME_SQL), reps=Sum("reps"), sets=Count("id"))

    muscle_sets = Counter()
    exercise_volume = Counter()
    pr_count = 0
    for workout in workouts:
        pr_count += sum(len(kinds) for kinds in personal_records(workout).values())
        for we in workout.exercises.all():
            n = len(we.sets.all())
            for muscle in we.exercise.primary_muscles or ["other"]:
                muscle_sets[muscle] += n
            exercise_volume[we.exercise.name] += float(sum(s.weight_kg * s.reps for s in we.sets.all()))

    days = max((end - start).days + 1, 1)
    length = end - start + timedelta(days=1)
    previous_volume = user_sets(user, start - length, start - timedelta(days=1)).aggregate(v=Sum(VOLUME_SQL))["v"] or 0
    volume = totals["volume"] or 0
    return {
        "start": start,
        "end": end,
        "workouts": len(workouts),
        "active_days": len({w.performed_on for w in workouts}),
        "sets": totals["sets"] or 0,
        "reps": totals["reps"] or 0,
        "volume_kg": round(volume, 1),
        "volume_change_pct": round((volume - previous_volume) / previous_volume * 100) if previous_volume else None,
        "pr_count": pr_count,
        "most_trained_muscle": muscle_sets.most_common(1)[0][0] if muscle_sets else None,
        "top_exercise": exercise_volume.most_common(1)[0][0] if exercise_volume else None,
        "longest_weekly_streak": _longest_weekly_streak([w.performed_on for w in workouts]),
        "workouts_per_week": round(len(workouts) / (days / 7), 1),
    }


# --- Leaderboards ------------------------------------------------------------------------

LEADERBOARD_TTL = 5 * 60


def weekly_leaderboard(user, week_start):
    """Friends (who opted in) + you, ranked by this week's training. Cached for 5 minutes."""
    key = f"leaderboard:{user.pk}:{week_start.isoformat()}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    week_end = week_start + timedelta(days=6)
    ids = {uid for uid in friend_ids(user.pk)}
    people = list(
        User.objects.filter(pk__in=ids, is_active=True, show_on_leaderboards=True).select_related("avatar")
    ) + [user]
    rows = []
    for person in people:
        workouts = list(
            Workout.objects.filter(user=person, performed_on__range=(week_start, week_end)).prefetch_related("exercises__sets")
        )
        volume = user_sets(person, week_start, week_end).aggregate(v=Sum(VOLUME_SQL))["v"] or 0
        rows.append(
            {
                "user_id": person.pk,
                "username": person.username,
                "volume_kg": round(volume, 1),
                "workouts": len(workouts),
                "prs": sum(len(k) for w in workouts for k in personal_records(w).values()),
                "is_me": person.pk == user.pk,
            }
        )
    result = {"week_start": week_start, "week_end": week_end, "rows": rows}
    cache.set(key, result, LEADERBOARD_TTL)
    return result


# --- Challenges ------------------------------------------------------------------------

def challenge_score(challenge, user):
    sets = user_sets(user, challenge.starts_on, challenge.ends_on)
    if challenge.metric == Challenge.Metric.WORKOUT_COUNT:
        return Workout.objects.filter(user=user, performed_on__range=(challenge.starts_on, challenge.ends_on)).count()
    if challenge.metric == Challenge.Metric.EXERCISE_VOLUME:
        sets = sets.filter(workout_exercise__exercise_id=challenge.exercise_id)
    return round(sets.aggregate(v=Sum(VOLUME_SQL))["v"] or 0, 1)


def finish_if_over(challenge, today=None):
    """Lazily settle a challenge once its last day has passed (also run daily by a command)."""
    today = today or date.today()
    if challenge.status != Challenge.Status.ACTIVE or challenge.ends_on >= today:
        return challenge
    creator_score = challenge_score(challenge, challenge.creator)
    opponent_score = challenge_score(challenge, challenge.opponent)
    if creator_score != opponent_score:
        challenge.winner = challenge.creator if creator_score > opponent_score else challenge.opponent
    challenge.status = Challenge.Status.FINISHED
    challenge.finished_at = timezone.now()
    challenge.save(update_fields=["winner", "status", "finished_at"])
    for participant, other in ((challenge.creator, challenge.opponent), (challenge.opponent, challenge.creator)):
        notify(
            participant,
            Notification.Kind.CHALLENGE_RESULT,
            actor=other,
            data={"challenge_id": challenge.pk, "won": challenge.winner_id == participant.pk, "draw": challenge.winner_id is None},
        )
    return challenge
