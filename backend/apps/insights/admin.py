from django.contrib import admin

from .models import BodyMetric, Challenge


@admin.register(BodyMetric)
class BodyMetricAdmin(admin.ModelAdmin):
    list_display = ["user", "measured_on", "bodyweight_kg"]


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = ["creator", "opponent", "metric", "starts_on", "ends_on", "status"]
    list_filter = ["status", "metric"]
