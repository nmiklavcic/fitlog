from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache


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
