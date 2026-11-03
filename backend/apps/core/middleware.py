import logging
import re
import time
import uuid

from django.utils.functional import SimpleLazyObject, empty

from .logging import request_id_var
from .utils import client_ip

logger = logging.getLogger("liftlog.request")

# Nginx sends its $request_id; accept only safe-looking values, otherwise make our own.
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
QUIET_PATHS = {"/api/health/", "/metrics"}


class RequestIDMiddleware:
    """Tags the request (and every log line written while handling it) with an ID."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.headers.get("X-Request-ID", "")
        if not REQUEST_ID_RE.match(request_id):
            request_id = uuid.uuid4().hex
        request.request_id = request_id
        token = request_id_var.set(request_id)
        try:
            response = self.get_response(request)
        finally:
            request_id_var.reset(token)
        response["X-Request-ID"] = request_id
        return response


def _resolved_user_id(request):
    # Only report the user if something already loaded it; touching request.user
    # here would force a session lookup (and fail loudly when Redis is down).
    user = request.__dict__.get("user")
    if user is None or (isinstance(user, SimpleLazyObject) and user._wrapped is empty):
        return None
    return user.pk if user.is_authenticated else None


class RequestLogMiddleware:
    """One structured access-log line per request, with timing."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        started = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - started) * 1000, 1)

        if request.path in QUIET_PATHS:
            level = logging.DEBUG
        elif response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING
        else:
            level = logging.INFO
        logger.log(
            level,
            "%s %s %s %sms",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            extra={
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "user_id": _resolved_user_id(request),
                "ip": client_ip(request),
            },
        )
        return response
