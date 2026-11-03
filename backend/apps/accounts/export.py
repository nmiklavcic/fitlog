"""GDPR data export (right of access / data portability): everything we store about a user."""
from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.social.models import Comment, Friendship, Like, Post
from apps.social.visibility import friend_ids
from apps.workouts.models import Exercise, Workout, WorkoutTemplate


def _workouts(user):
    workouts = Workout.objects.filter(user=user).prefetch_related("exercises__exercise", "exercises__sets")
    return [
        {
            "id": w.id,
            "title": w.title,
            "performed_on": w.performed_on,
            "started_at": w.started_at,
            "finished_at": w.finished_at,
            "notes": w.notes,
            "exercises": [
                {
                    "exercise": we.exercise.name,
                    "notes": we.notes,
                    "sets": [{"weight_kg": float(s.weight_kg), "reps": s.reps} for s in we.sets.all()],
                }
                for we in w.exercises.all()
            ],
        }
        for w in workouts
    ]


def build_export(user):
    User = get_user_model()
    data = {
        "exported_at": timezone.now(),
        "profile": {
            "username": user.username,
            "email": user.email,
            "bio": user.bio,
            "is_public": user.is_public,
            "units": user.units,
            "show_on_leaderboards": user.show_on_leaderboards,
            "two_factor_enabled": user.totp_enabled,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
        },
        "workouts": _workouts(user),
        "templates": [
            {
                "name": t.name,
                "notes": t.notes,
                "exercises": [
                    {"exercise": te.exercise.name, "target_sets": te.target_sets, "target_reps": te.target_reps}
                    for te in t.exercises.all()
                ],
            }
            for t in WorkoutTemplate.objects.filter(user=user).prefetch_related("exercises__exercise")
        ],
        "custom_exercises": list(
            Exercise.objects.filter(owner=user).values("name", "category", "equipment", "primary_muscles")
        ),
        "posts": list(Post.objects.filter(author=user).values("id", "kind", "caption", "stats", "recap_period", "created_at")),
        "comments": list(Comment.objects.filter(author=user).values("post_id", "body", "created_at")),
        "likes": list(Like.objects.filter(user=user).values("post_id", "created_at")),
        "friends": list(User.objects.filter(pk__in=friend_ids(user.pk)).values_list("username", flat=True)),
        "pending_friend_requests_sent": list(
            Friendship.objects.filter(requester=user, status=Friendship.Status.PENDING).values_list(
                "addressee__username", flat=True
            )
        ),
    }
    # Premium data, if those apps are installed.
    if apps.is_installed("apps.insights"):
        BodyMetric = apps.get_model("insights", "BodyMetric")
        data["body_metrics"] = list(BodyMetric.objects.filter(user=user).values().order_by("measured_on"))
    subscription = getattr(user, "subscription", None)
    if subscription is not None:
        data["subscription"] = {
            "plan": subscription.plan,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
        }
    return data
