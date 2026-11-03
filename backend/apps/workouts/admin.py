from django.contrib import admin

from .models import Exercise, Workout, WorkoutTemplate


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "equipment", "owner"]
    list_filter = ["category", "equipment"]
    search_fields = ["name"]


@admin.register(Workout)
class WorkoutAdmin(admin.ModelAdmin):
    list_display = ["user", "performed_on", "title"]
    date_hierarchy = "performed_on"


@admin.register(WorkoutTemplate)
class WorkoutTemplateAdmin(admin.ModelAdmin):
    list_display = ["user", "name"]
