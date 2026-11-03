from django.contrib import admin
from django.urls import include, path
from django_prometheus import exports

from apps.core import views as core_views

api_patterns = [
    path("health/", core_views.health, name="health"),
    path("auth/", include("apps.accounts.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
    # Scraped by Prometheus directly on Gunicorn's port; Nginx blocks it publicly.
    path("metrics", exports.ExportToDjangoView, name="prometheus-metrics"),
]
