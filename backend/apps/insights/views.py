"""Premium endpoints. Every view here is gated by IsPremium (HTTP 402 for free users),
except accepting/declining/viewing a challenge you were invited to."""
from datetime import date, timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.images import process_upload
from apps.core.metrics import POSTS_CREATED
from apps.core.permissions import IsPremium
from apps.social.models import Notification, Post
from apps.social.services import notify
from apps.social.views import annotated_posts
from apps.social.serializers import PostSerializer

from . import services
from .models import BodyMetric, Challenge
from .recap_image import render_recap
from .serializers import BodyMetricSerializer, ChallengeSerializer


class PremiumAPIView(APIView):
    permission_classes = APIView.permission_classes + [IsPremium]


def int_param(request, name, default, lowest, highest):
    try:
        value = int(request.query_params.get(name, default))
    except ValueError:
        raise serializers.ValidationError({name: "Must be a number."})
    return max(lowest, min(highest, value))


class MuscleVolumeView(PremiumAPIView):
    def get(self, request):
        return Response(services.muscle_volume(request.user, weeks=int_param(request, "weeks", 12, 1, 52)))


class HeatmapView(PremiumAPIView):
    def get(self, request):
        return Response(services.heatmap(request.user, int_param(request, "year", date.today().year, 2000, 2100)))


class E1rmTrendsView(PremiumAPIView):
    def get(self, request):
        return Response({"exercises": services.e1rm_trends(request.user)})


class BodyMetricViewSet(viewsets.ModelViewSet):
    serializer_class = BodyMetricSerializer
    permission_classes = viewsets.ModelViewSet.permission_classes + [IsPremium]

    def get_queryset(self):
        return BodyMetric.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        # One check-in per day: logging the same day again updates it.
        existing = self.get_queryset().filter(measured_on=request.data.get("measured_on")).first()
        serializer = self.get_serializer(existing, data=request.data, partial=existing is not None)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=status.HTTP_200_OK if existing else status.HTTP_201_CREATED)

    @action(detail=False)
    def summary(self, request):
        entries = self.get_queryset().exclude(bodyweight_kg__isnull=True)
        latest = entries.first()
        month_ago = entries.filter(measured_on__lte=date.today() - timedelta(days=30)).first()
        bodyweight = latest.bodyweight_kg if latest else None
        return Response(
            {
                "latest_bodyweight_kg": bodyweight,
                "change_30d_kg": round(float(bodyweight - month_ago.bodyweight_kg), 2) if latest and month_ago else None,
                "relative_strength": services.relative_strength(request.user, bodyweight),
            }
        )


def recap_period(request_data):
    month, year = request_data.get("month"), request_data.get("year")
    try:
        if month:
            return services.period_bounds(month=str(month))
        if year:
            return services.period_bounds(year=int(year))
    except ValueError:
        pass
    raise serializers.ValidationError({"detail": "Pass ?month=YYYY-MM or ?year=YYYY."})


class RecapView(PremiumAPIView):
    def get(self, request):
        start, end, label, period = recap_period(request.query_params)
        return Response({"label": label, "period": period, **services.recap(request.user, start, end)})


class RecapShareView(PremiumAPIView):
    def post(self, request):
        start, end, label, period = recap_period(request.data)
        if Post.objects.filter(author=request.user, kind=Post.Kind.RECAP, recap_period=period).exists():
            return Response({"detail": "You already shared this recap."}, status=status.HTTP_409_CONFLICT)
        stats = services.recap(request.user, start, end)
        if stats["workouts"] == 0:
            return Response({"detail": "No workouts in this period yet."}, status=status.HTTP_400_BAD_REQUEST)
        photo = process_upload(render_recap(label, stats, request.user.username, request.user.units))
        post = Post.objects.create(
            author=request.user,
            kind=Post.Kind.RECAP,
            recap_period=period,
            stats={"label": label, **{k: (v.isoformat() if isinstance(v, date) else v) for k, v in stats.items()}},
            photo=photo,
            caption=str(request.data.get("caption", ""))[:2200].strip(),
        )
        POSTS_CREATED.labels(Post.Kind.RECAP).inc()
        post = annotated_posts(request.user).get(pk=post.pk)
        return Response(PostSerializer(post, context={"request": request}).data, status=status.HTTP_201_CREATED)


class LeaderboardView(PremiumAPIView):
    def get(self, request):
        try:
            day = date.fromisoformat(request.query_params.get("week", date.today().isoformat()))
        except ValueError:
            raise serializers.ValidationError({"week": "Use the YYYY-MM-DD format."})
        week_start = day - timedelta(days=day.weekday())
        return Response(services.weekly_leaderboard(request.user, week_start))


class ChallengeViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    serializer_class = ChallengeSerializer

    def get_permissions(self):
        # Creating needs Premium; your friend can accept and follow along for free.
        if self.action == "create":
            return super().get_permissions() + [IsPremium()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        return Challenge.objects.filter(Q(creator=user) | Q(opponent=user)).select_related(
            "creator__avatar", "opponent__avatar", "exercise"
        )

    def list(self, request):
        challenges = [services.finish_if_over(c) for c in self.get_queryset()[:50]]
        return Response(self.get_serializer(challenges, many=True).data)

    def retrieve(self, request, pk=None):
        challenge = services.finish_if_over(self.get_object())
        return Response(self.get_serializer(challenge).data)

    def perform_create(self, serializer):
        challenge = serializer.save(creator=self.request.user)
        notify(challenge.opponent, Notification.Kind.CHALLENGE_INVITE, actor=self.request.user, data={"challenge_id": challenge.pk})

    def destroy(self, request, pk=None):
        challenge = get_object_or_404(self.get_queryset(), pk=pk, creator=request.user, status=Challenge.Status.PENDING)
        challenge.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _respond(self, request, pk, accept):
        challenge = get_object_or_404(self.get_queryset(), pk=pk, opponent=request.user, status=Challenge.Status.PENDING)
        challenge.status = Challenge.Status.ACTIVE if accept else Challenge.Status.DECLINED
        challenge.save(update_fields=["status"])
        if accept:
            notify(challenge.creator, Notification.Kind.CHALLENGE_ACCEPT, actor=request.user, data={"challenge_id": challenge.pk})
        return Response(self.get_serializer(challenge).data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        return self._respond(request, pk, accept=True)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        return self._respond(request, pk, accept=False)
