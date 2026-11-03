from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.utils._os import safe_join
from django.views.decorators.cache import never_cache

from . import signing


def csrf_failure(request, reason=""):
    """JSON instead of Django's HTML page, so the SPA can show a useful error."""
    return JsonResponse({"detail": "CSRF check failed. Reload the page and try again."}, status=403)


@never_cache
def health(request):
    """Readiness check for load balancers / uptime monitors.

    A plain Django view (not DRF) on purpose: it must not touch the session,
    which lives in Redis and would make the check crash instead of report.
    """
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report any failure
        checks["database"] = f"error: {exc.__class__.__name__}"
    try:
        cache.set("health:ping", "pong", 5)
        checks["redis"] = "ok" if cache.get("health:ping") == "pong" else "error: bad read"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc.__class__.__name__}"

    healthy = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks, "version": settings.APP_VERSION},
        status=200 if healthy else 503,
    )


def signed_media(request, path):
    """DEBUG-only stand-in for Nginx's secure_link location, so local dev behaves the same."""
    result = signing.check(request.path, request.GET.get("e"), request.GET.get("s"))
    if result == "invalid":
        return HttpResponse("Forbidden", status=403)
    if result == "expired":
        return HttpResponse("Link expired", status=410)
    try:
        file_path = Path(safe_join(settings.MEDIA_ROOT, path))
    except ValueError:  # path traversal attempt
        raise Http404
    if not file_path.is_file():
        raise Http404
    response = FileResponse(file_path.open("rb"), content_type="image/webp")
    response["Cache-Control"] = "private, max-age=3600"
    return response
