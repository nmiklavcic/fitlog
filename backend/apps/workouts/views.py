import hashlib
from datetime import date, timedelta

from django.core.cache import cache
from django.db.models import Case, Count, F, FloatField, IntegerField, Q, Sum, Value, When
from django.db.models.functions import Cast
from django.contrib.postgres.search import TrigramWordSimilarity
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.metrics import WORKOUTS_LOGGED
from apps.core.permissions import require_premium

from .models import Exercise, TemplateExercise, Workout, WorkoutExercise, WorkoutTemplate
from .serializers import ExerciseSerializer, TemplateSerializer, WorkoutSerializer
from .services import exercise_progress, last_session

SEARCH_LIMIT = 40
SEARCH_CACHE_SECONDS = 60 * 60
FREE_PROGRESS_DAYS = 90


def parse_date(value, field):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise serializers.ValidationError({field: "Use the YYYY-MM-DD format."})


def search_catalogue(query, filters):
    """Fuzzy search over the shared catalogue, cached in Redis for an hour.

    Ranking: names starting with the query first, then by trigram word
    similarity, which tolerates typos ("bench pres") and partial words.
    """
    key_source = f"{query.lower()}|{sorted(filters.items())}"
    key = "exsearch:" + hashlib.sha256(key_source.encode()).hexdigest()[:32]
    cached = cache.get(key)
    if cached is not None:
        return cached

    qs = Exercise.objects.filter(owner__isnull=True, **filters)
    if query:
        qs = (
            qs.annotate(
                similarity=TrigramWordSimilarity(query, "name"),
                prefix_rank=Case(
                    When(name__istartswith=query, then=Value(0)), default=Value(1), output_field=IntegerField()
                ),
            )
            .filter(Q(name__icontains=query) | Q(similarity__gte=0.4))
            .order_by("prefix_rank", "-similarity", "name")
        )
    ids = list(qs.values_list("id", flat=True)[:SEARCH_LIMIT])
    cache.set(key, ids, SEARCH_CACHE_SECONDS)
    return ids


class ExerciseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Catalogue + custom exercises. Custom ones are private to their owner."""

    serializer_class = ExerciseSerializer

    def get_queryset(self):
        return Exercise.objects.visible_to(self.request.user)

    def list(self, request):
        query = request.query_params.get("q", "").strip()[:100]
        filters = {}
        if muscle := request.query_params.get("muscle"):
            filters["primary_muscles__contains"] = [muscle]
        if equipment := request.query_params.get("equipment"):
            filters["equipment"] = equipment
        if category := request.query_params.get("category"):
            filters["category"] = category

        # The user's own custom exercises are matched live (never cached: they're private).
        custom = Exercise.objects.filter(owner=request.user, **filters)
        if query:
            custom = custom.filter(name__icontains=query)
        catalogue_ids = search_catalogue(query, filters)
        catalogue = {e.id: e for e in Exercise.objects.filter(id__in=catalogue_ids)}
        results = list(custom[:10]) + [catalogue[i] for i in catalogue_ids if i in catalogue]
        return Response(ExerciseSerializer(results, many=True, context={"request": request}).data)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def destroy(self, request, *args, **kwargs):
        exercise = self.get_object()
        if exercise.owner_id != request.user.id:
            return Response({"detail": "Only custom exercises can be deleted."}, status=status.HTTP_403_FORBIDDEN)
        in_use = (
            WorkoutExercise.objects.filter(exercise=exercise).exists()
            or TemplateExercise.objects.filter(exercise=exercise).exists()
        )
        if in_use:
            return Response(
                {"detail": "This exercise is used in your workouts or templates."}, status=status.HTTP_409_CONFLICT
            )
        exercise.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True)
    def progress(self, request, pk=None):
        """Per-day progress. Free: last 90 days. Premium: any range (?range=365|all)."""
        exercise = self.get_object()
        requested = request.query_params.get("range", str(FREE_PROGRESS_DAYS))
        if requested != str(FREE_PROGRESS_DAYS):
            require_premium(request.user)
        since = None if requested == "all" else date.today() - timedelta(days=int(requested) if requested.isdigit() else FREE_PROGRESS_DAYS)
        return Response(
            {
                "exercise": {"id": exercise.id, "name": exercise.name},
                "range": requested,
                "points": exercise_progress(request.user, exercise.id, since),
            }
        )

    @action(detail=True)
    def last(self, request, pk=None):
        """The sets from the last time you did this exercise ("previous" column in the logger)."""
        exercise = self.get_object()
        return Response(last_session(request.user, exercise.id))


class WorkoutViewSet(viewsets.ModelViewSet):
    """The user's own workouts. Other users' workouts are never visible (404)."""

    serializer_class = WorkoutSerializer

    def get_queryset(self):
        return (
            Workout.objects.filter(user=self.request.user)
            .prefetch_related("exercises__exercise", "exercises__sets")
        )

    def list(self, request):
        today = date.today()
        start = parse_date(request.query_params["from"], "from") if "from" in request.query_params else today - timedelta(days=30)
        end = parse_date(request.query_params["to"], "to") if "to" in request.query_params else today
        if end < start or (end - start).days > 366:
            raise serializers.ValidationError({"to": "The range must be between 0 and 366 days."})
        workouts = self.get_queryset().filter(performed_on__range=(start, end))
        return Response(self.get_serializer(workouts, many=True).data)

    def perform_create(self, serializer):
        serializer.save()
        WORKOUTS_LOGGED.inc()

    @action(detail=False)
    def calendar(self, request):
        """Workout days in a month: ?month=YYYY-MM -> {"days": {"2026-11-03": [...]}}."""
        month = request.query_params.get("month") or date.today().strftime("%Y-%m")
        first = parse_date(f"{month}-01", "month")
        next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        rows = (
            Workout.objects.filter(user=request.user, performed_on__gte=first, performed_on__lt=next_month)
            .annotate(
                exercise_count=Count("exercises", distinct=True),
                set_count=Count("exercises__sets"),
                volume=Sum(Cast(F("exercises__sets__weight_kg") * F("exercises__sets__reps"), FloatField())),
            )
            .order_by("performed_on", "created_at")
        )
        days = {}
        for w in rows:
            days.setdefault(w.performed_on.isoformat(), []).append(
                {
                    "id": w.id,
                    "title": w.title,
                    "exercise_count": w.exercise_count,
                    "set_count": w.set_count,
                    "volume_kg": round(w.volume or 0, 1),
                    "post_id": getattr(getattr(w, "post", None), "id", None),
                }
            )
        return Response({"month": month, "days": days})

    @action(detail=True, methods=["post"], url_path="save-as-template")
    def save_as_template(self, request, pk=None):
        workout = self.get_object()
        name = (request.data.get("name") or workout.title or f"Workout {workout.performed_on}").strip()[:100]
        template = WorkoutTemplate.objects.create(user=request.user, name=name, notes=workout.notes)
        TemplateExercise.objects.bulk_create(
            TemplateExercise(
                template=template,
                exercise_id=we.exercise_id,
                order=we.order,
                target_sets=min(max(len(we.sets.all()), 1), 20),
                target_reps=min(max((s.reps for s in we.sets.all()), default=10), 100),
            )
            for we in workout.exercises.all()
        )
        return Response(TemplateSerializer(template, context={"request": request}).data, status=status.HTTP_201_CREATED)


class TemplateViewSet(viewsets.ModelViewSet):
    serializer_class = TemplateSerializer

    def get_queryset(self):
        return WorkoutTemplate.objects.filter(user=self.request.user).prefetch_related("exercises__exercise")

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """A pre-filled workout draft: last session's weights for each exercise."""
        template = self.get_object()
        exercises = []
        for te in template.exercises.all():
            previous = last_session(request.user, te.exercise_id)
            previous_sets = previous["sets"] if previous else []
            sets = []
            for i in range(te.target_sets):
                if i < len(previous_sets):
                    sets.append(previous_sets[i])
                elif previous_sets:
                    sets.append({"weight_kg": previous_sets[-1]["weight_kg"], "reps": te.target_reps})
                else:
                    sets.append({"weight_kg": 0, "reps": te.target_reps})
            exercises.append(
                {
                    "exercise": {
                        "id": te.exercise.id,
                        "name": te.exercise.name,
                        "category": te.exercise.category,
                        "equipment": te.exercise.equipment,
                        "primary_muscles": te.exercise.primary_muscles,
                    },
                    "previous": previous,
                    "sets": sets,
                }
            )
        return Response({"title": template.name, "template_id": template.id, "exercises": exercises})
