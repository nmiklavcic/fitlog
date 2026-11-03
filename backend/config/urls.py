from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django_prometheus import exports

from apps.billing.webhooks import stripe_webhook
from apps.core import views as core_views

api_patterns = [
    path("health/", core_views.health, name="health"),
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.workouts.urls")),
    path("", include("apps.social.urls")),
    path("billing/", include("apps.billing.urls")),
    path("billing/webhook/", stripe_webhook, name="stripe-webhook"),
    path("", include("apps.insights.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
    # Scraped by Prometheus directly on Gunicorn's port; Nginx blocks it publicly.
    path("metrics", exports.ExportToDjangoView, name="prometheus-metrics"),
]

if settings.DEBUG:
    # In production Nginx serves /media/ itself after checking the signature.
    urlpatterns += [re_path(r"^media/(?P<path>.+)$", core_views.signed_media, name="signed-media")]
