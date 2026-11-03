from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("body-metrics", views.BodyMetricViewSet, basename="body-metric")
router.register("challenges", views.ChallengeViewSet, basename="challenge")

urlpatterns = [
    path("analytics/muscle-volume/", views.MuscleVolumeView.as_view(), name="analytics-muscle-volume"),
    path("analytics/heatmap/", views.HeatmapView.as_view(), name="analytics-heatmap"),
    path("analytics/e1rm-trends/", views.E1rmTrendsView.as_view(), name="analytics-e1rm-trends"),
    path("recap/", views.RecapView.as_view(), name="recap"),
    path("recap/share/", views.RecapShareView.as_view(), name="recap-share"),
    path("leaderboards/weekly/", views.LeaderboardView.as_view(), name="leaderboard-weekly"),
] + router.urls
