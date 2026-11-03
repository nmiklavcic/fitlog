from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("exercises", views.ExerciseViewSet, basename="exercise")
router.register("workouts", views.WorkoutViewSet, basename="workout")
router.register("templates", views.TemplateViewSet, basename="template")

urlpatterns = router.urls
