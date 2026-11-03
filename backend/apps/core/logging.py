"""Structured logging: every line is one JSON object, tagged with the request ID."""
import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

request_id_var = ContextVar("request_id", default=None)

# Attributes every LogRecord has; anything else was passed via `extra=` and is
# copied into the JSON payload.
_RESERVED = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
    "request",  # Django attaches the HttpRequest object; not useful in a log line
}


class RequestContextFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get() or "-"
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_") and value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)
