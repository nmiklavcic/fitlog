import time

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.metrics import LOGINS, SIGNUPS
from apps.core.utils import client_ip

from . import security
from .models import User
from .security import security_log
from .serializers import (
    LoginSerializer,
    MeSerializer,
    MeUpdateSerializer,
    PasswordChangeSerializer,
    RegisterSerializer,
)

PENDING_2FA_KEY = "pending_2fa"


class PublicAuthView(APIView):
    """Base for endpoints used before login (register, login, password reset).

    DRF skips CSRF checks for anonymous requests, so we enforce it explicitly
    to prevent login CSRF (an attacker silently logging you into their account).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]

    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


def me_response(request, user, status_code=status.HTTP_200_OK):
    return Response(MeSerializer(user, context={"request": request}).data, status=status_code)


class CsrfView(APIView):
    """Sets the csrftoken cookie; the SPA calls this once on startup."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


class RegisterView(PublicAuthView):
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        SIGNUPS.inc()
        security_log.info("signup", extra={"event": "signup", "user_id": user.pk, "ip": client_ip(request)})
        return me_response(request, user, status.HTTP_201_CREATED)


def account_key(identifier):
    """Normalise 'username or email' to the username, so both share one lockout counter."""
    if "@" in identifier:
        user = User.objects.filter(email__iexact=identifier).only("username").first()
        if user:
            return user.username
    return identifier


class LoginView(PublicAuthView):
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = account_key(serializer.validated_data["username"].strip())
        ip = client_ip(request)

        if security.is_locked_out(username):
            LOGINS.labels("locked").inc()
            security_log.warning("login_locked", extra={"event": "login_locked", "username": username, "ip": ip})
            return Response(
                {"detail": "Too many failed attempts. Try again in 15 minutes."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        user = authenticate(request, username=username, password=serializer.validated_data["password"])
        if user is None:
            failures = security.register_failure(username)
            LOGINS.labels("failure").inc()
            security_log.warning(
                "login_failed", extra={"event": "login_failed", "username": username, "ip": ip, "failures": failures}
            )
            # Same message whether the user exists or not (no account enumeration).
            return Response({"detail": "Invalid username or password."}, status=status.HTTP_400_BAD_REQUEST)

        security.clear_failures(username)
        if user.totp_enabled:
            # Password is right, but don't log in yet: remember who passed step 1.
            request.session.cycle_key()
            request.session[PENDING_2FA_KEY] = {"user_id": user.pk, "ts": int(time.time()), "attempts": 0}
            LOGINS.labels("2fa_required").inc()
            return Response({"two_factor_required": True})

        login(request, user)  # rotates the session key (prevents session fixation)
        LOGINS.labels("success").inc()
        security_log.info("login_success", extra={"event": "login_success", "user_id": user.pk, "ip": ip})
        return me_response(request, user)


class LogoutView(PublicAuthView):
    throttle_classes = []

    def post(self, request):
        if request.user.is_authenticated:
            security_log.info("logout", extra={"event": "logout", "user_id": request.user.pk})
        logout(request)  # deletes the session from Redis
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return me_response(request, request.user)

    def patch(self, request):
        serializer = MeUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return me_response(request, request.user)


class PasswordChangeView(APIView):
    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        # The session hash depends on the password, so all *other* sessions are now
        # invalid; this keeps the current one logged in.
        update_session_auth_hash(request, request.user)
        security_log.info("password_changed", extra={"event": "password_changed", "user_id": request.user.pk})
        return Response({"detail": "Password changed."})
