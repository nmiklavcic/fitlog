"""
Django settings for Liftlog.

Every deployment-specific value comes from an environment variable so the same
code runs on a laptop (backend/dev.env) and on a VM (/etc/liftlog/liftlog.env,
loaded by systemd's EnvironmentFile=). See docs/deploy/liftlog.env.example.
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core ---------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is off.")
    SECRET_KEY = "dev-only-not-a-secret"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Public URL of the site, used to build links in emails and Stripe redirects.
PUBLIC_BASE_URL = env("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
APP_VERSION = env("APP_VERSION", "dev")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "django_prometheus",
    "apps.core",
    "apps.accounts",
    "apps.workouts",
    "apps.social",
]

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "apps.core.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.RequestLogMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database (PostgreSQL) ----------------------------------------------------
# An empty DB_HOST means "connect over the local Unix socket", which lets the
# app use PostgreSQL peer authentication (no password) on the VM.

DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": env("DB_NAME", "liftlog"),
        "USER": env("DB_USER", "liftlog"),
        "PASSWORD": env("DB_PASSWORD", ""),
        "HOST": env("DB_HOST", ""),
        "PORT": env("DB_PORT", ""),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Cache + sessions (Redis) -------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "KEY_PREFIX": "liftlog",
        "TIMEOUT": 300,
    }
}

# Sessions live only in Redis: logout deletes the key, so the session is gone server-side.
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
# The SPA reads the CSRF cookie and echoes it in the X-CSRFToken header.
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

# --- Security headers (Nginx terminates TLS and sets X-Forwarded-Proto) -------

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not DEBUG)
# Health checks and Prometheus scrapes hit Gunicorn directly over plain HTTP.
SECURE_REDIRECT_EXEMPT = [r"^api/health/$", r"^metrics$"]
SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

# --- Auth ---------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

# Argon2id first (memory-hard, winner of the Password Hashing Competition);
# PBKDF2 stays as a fallback so old hashes can still be verified and upgraded.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_RESET_TIMEOUT = 60 * 60  # reset links expire after 1 hour

# Failed-login lockout (per username, stored in Redis).
LOGIN_FAILURE_LIMIT = env_int("LOGIN_FAILURE_LIMIT", 5)
LOGIN_LOCKOUT_SECONDS = env_int("LOGIN_LOCKOUT_SECONDS", 15 * 60)

# --- Django REST Framework ----------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["apps.core.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        "login": "10/min",
        "two_factor": "10/min",
        "register": "10/hour",
        "password_reset": "5/hour",
        "upload": "60/hour",
    },
    # Nginx is the only proxy in front of Gunicorn: DRF takes the client IP from
    # the last X-Forwarded-For entry, the one Nginx appended.
    "NUM_PROXIES": 1,
    # Return decimals (weights) as JSON numbers instead of strings.
    "COERCE_DECIMAL_TO_STRING": False,
}

# --- Static files and uploaded media -------------------------------------------

STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", str(BASE_DIR / "staticfiles"))
MEDIA_URL = "/media/"
MEDIA_ROOT = env("MEDIA_ROOT", str(BASE_DIR / "media"))
STORAGES = {
    # Swap this backend for django-storages' S3 backend to move media to object storage.
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
        )
    },
}

# Shared with Nginx's secure_link_md5 directive; see apps/core/signing.py.
MEDIA_URL_SIGNING_SECRET = env("MEDIA_URL_SIGNING_SECRET")
if not MEDIA_URL_SIGNING_SECRET:
    if not DEBUG:
        raise ImproperlyConfigured("MEDIA_URL_SIGNING_SECRET must be set when DJANGO_DEBUG is off.")
    MEDIA_URL_SIGNING_SECRET = "dev-only-media-secret"
MEDIA_URL_TTL_SECONDS = env_int("MEDIA_URL_TTL_SECONDS", 6 * 60 * 60)
MAX_UPLOAD_BYTES = env_int("MAX_UPLOAD_BYTES", 10 * 1024 * 1024)

# --- Email (console output unless an SMTP host is configured) -------------------

EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "Liftlog <no-reply@localhost>")

# --- Internationalisation -----------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", "Europe/Ljubljana")
USE_I18N = True
USE_TZ = True

# --- Logging (JSON to stdout -> journald -> Loki/Promtail/Alloy) ---------------

LOG_LEVEL = env("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = env("LOG_FORMAT", "json")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_context": {"()": "apps.core.logging.RequestContextFilter"}},
    "formatters": {
        "json": {"()": "apps.core.logging.JSONFormatter"},
        "text": {"format": "%(asctime)s %(levelname)-7s %(name)s [%(request_id)s] %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "json" if LOG_FORMAT == "json" else "text",
            "filters": ["request_context"],
        }
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # Our request middleware already logs every request; keep django.request for 5xx tracebacks.
        "django.request": {"level": "ERROR", "propagate": True},
        "django.server": {"level": "WARNING", "propagate": True},
    },
}
