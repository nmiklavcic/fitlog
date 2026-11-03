import json
import time

from django.conf import settings
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import HttpResponse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.billing.services import cancel_for_account_deletion
from apps.core.images import delete_photo_if_unused, process_upload
from apps.core.metrics import LOGINS, SIGNUPS
from apps.core.utils import client_ip

from . import security, totp
from .export import build_export
from .models import User
from .security import security_log
from .serializers import (
    LoginSerializer,
    MeSerializer,
    MeUpdateSerializer,
    PasswordChangeSerializer,
    RegisterSerializer,
    check_password_strength,
)

PENDING_2FA_KEY = "pending_2fa"
PENDING_2FA_SECONDS = 5 * 60
PENDING_2FA_MAX_ATTEMPTS = 5
TOTP_SETUP_KEY = "totp_setup_secret"


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


class MeAvatarView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "upload"

    def post(self, request):
        photo = process_upload(request.FILES.get("photo"))
        old_photo_id = request.user.avatar_id
        request.user.avatar = photo
        request.user.save(update_fields=["avatar"])
        if old_photo_id and old_photo_id != photo.pk:
            delete_photo_if_unused(old_photo_id)
        return me_response(request, request.user)

    def delete(self, request):
        old_photo_id = request.user.avatar_id
        request.user.avatar = None
        request.user.save(update_fields=["avatar"])
        if old_photo_id:
            delete_photo_if_unused(old_photo_id)
        return me_response(request, request.user)


# --- Two-factor authentication ------------------------------------------------------


class LoginTwoFactorView(PublicAuthView):
    """Step 2 of login: the 6-digit code (or a recovery code) for the user who passed step 1."""

    throttle_scope = "two_factor"

    def post(self, request):
        pending = request.session.get(PENDING_2FA_KEY)
        if not pending or time.time() - pending["ts"] > PENDING_2FA_SECONDS:
            request.session.pop(PENDING_2FA_KEY, None)
            return Response({"detail": "Your login expired. Enter your password again."}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(pk=pending["user_id"], is_active=True).first()
        code = str(request.data.get("code", ""))
        if user is None:
            request.session.pop(PENDING_2FA_KEY, None)
            return Response({"detail": "Your login expired. Enter your password again."}, status=status.HTTP_400_BAD_REQUEST)

        if totp.verify_code(user, code) or totp.use_recovery_code(user, code):
            request.session.pop(PENDING_2FA_KEY, None)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            LOGINS.labels("success").inc()
            security_log.info("login_success", extra={"event": "login_success", "user_id": user.pk, "ip": client_ip(request), "two_factor": True})
            return me_response(request, user)

        pending["attempts"] += 1
        security_log.warning("two_factor_failed", extra={"event": "two_factor_failed", "user_id": user.pk, "ip": client_ip(request)})
        if pending["attempts"] >= PENDING_2FA_MAX_ATTEMPTS:
            request.session.pop(PENDING_2FA_KEY, None)
            return Response({"detail": "Too many wrong codes. Log in again."}, status=status.HTTP_400_BAD_REQUEST)
        request.session[PENDING_2FA_KEY] = pending
        return Response({"detail": "That code isn't valid."}, status=status.HTTP_400_BAD_REQUEST)


class TwoFactorSetupView(APIView):
    """Step 1 of enabling 2FA: a new secret, kept in the session until confirmed."""

    def post(self, request):
        if request.user.totp_enabled:
            return Response({"detail": "Two-factor authentication is already on."}, status=status.HTTP_400_BAD_REQUEST)
        secret = totp.new_secret()
        request.session[TOTP_SETUP_KEY] = secret
        return Response({"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, request.user.username)})


class TwoFactorConfirmView(APIView):
    """Step 2: prove the app works by entering a code; returns one-time recovery codes."""

    def post(self, request):
        secret = request.session.get(TOTP_SETUP_KEY)
        if not secret:
            return Response({"detail": "Start the setup again."}, status=status.HTTP_400_BAD_REQUEST)
        step = totp.matching_step(secret, str(request.data.get("code", "")))
        if step is None:
            return Response({"code": ["That code isn't valid. Check your phone's clock."]}, status=status.HTTP_400_BAD_REQUEST)
        codes, hashes = totp.generate_recovery_codes()
        user = request.user
        user.totp_secret = secret
        user.totp_enabled = True
        user.totp_last_step = step
        user.recovery_codes = hashes
        user.save(update_fields=["totp_secret", "totp_enabled", "totp_last_step", "recovery_codes"])
        del request.session[TOTP_SETUP_KEY]
        security_log.info("two_factor_enabled", extra={"event": "two_factor_enabled", "user_id": user.pk})
        return Response({"recovery_codes": codes})


class TwoFactorDisableView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "two_factor"

    def post(self, request):
        user = request.user
        if not user.totp_enabled:
            return Response({"detail": "Two-factor authentication is already off."}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(str(request.data.get("password", ""))):
            return Response({"password": ["Password is incorrect."]}, status=status.HTTP_400_BAD_REQUEST)
        code = str(request.data.get("code", ""))
        if not (totp.verify_code(user, code) or totp.use_recovery_code(user, code)):
            return Response({"code": ["That code isn't valid."]}, status=status.HTTP_400_BAD_REQUEST)
        user.totp_secret = ""
        user.totp_enabled = False
        user.totp_last_step = None
        user.recovery_codes = []
        user.save(update_fields=["totp_secret", "totp_enabled", "totp_last_step", "recovery_codes"])
        security_log.info("two_factor_disabled", extra={"event": "two_factor_disabled", "user_id": user.pk})
        return me_response(request, user)


# --- Password reset by email -------------------------------------------------------------


class PasswordResetRequestView(PublicAuthView):
    throttle_scope = "password_reset"

    def post(self, request):
        email = str(request.data.get("email", "")).strip().lower()
        user = User.objects.filter(email__iexact=email, is_active=True).first() if email else None
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            link = f"{settings.PUBLIC_BASE_URL}/reset-password/{uid}/{token}"
            try:
                send_mail(
                    "Reset your Liftlog password",
                    f"Hi {user.username},\n\nSomeone (hopefully you) asked to reset your Liftlog password.\n"
                    f"Open this link within an hour to choose a new one:\n\n{link}\n\n"
                    "If you didn't ask for this, you can ignore this email.",
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                )
                security_log.info("password_reset_requested", extra={"event": "password_reset_requested", "user_id": user.pk})
            except Exception:  # noqa: BLE001 - never reveal mail problems to the caller
                security_log.exception("password_reset_mail_failed", extra={"event": "password_reset_mail_failed", "user_id": user.pk})
        # Same answer whether or not the account exists (no account enumeration).
        return Response({"detail": "If an account uses that email, we've sent it a reset link."})


class PasswordResetConfirmView(PublicAuthView):
    throttle_scope = "password_reset"

    def post(self, request):
        try:
            user_id = force_str(urlsafe_base64_decode(str(request.data.get("uid", ""))))
            user = User.objects.get(pk=user_id, is_active=True)
        except (ValueError, TypeError, OverflowError, User.DoesNotExist):
            user = None
        # The token is an HMAC over the user's password hash and last login, so it
        # stops working as soon as it's used (the password changes) or after 1 hour.
        if user is None or not default_token_generator.check_token(user, str(request.data.get("token", ""))):
            return Response({"detail": "This reset link is invalid or has expired."}, status=status.HTTP_400_BAD_REQUEST)
        new_password = str(request.data.get("new_password", ""))
        check_password_strength(new_password, user, field="new_password")
        user.set_password(new_password)
        user.save(update_fields=["password"])
        security.clear_failures(user.username)
        security_log.info("password_reset_done", extra={"event": "password_reset_done", "user_id": user.pk})
        return Response({"detail": "Password changed. You can log in now."})


# --- Data export and account deletion ---------------------------------------------------------


class ExportView(APIView):
    def get(self, request):
        body = json.dumps(build_export(request.user), cls=DjangoJSONEncoder, indent=2)
        response = HttpResponse(body, content_type="application/json")
        response["Content-Disposition"] = f'attachment; filename="liftlog-{request.user.username}.json"'
        security_log.info("data_exported", extra={"event": "data_exported", "user_id": request.user.pk})
        return response


class DeleteAccountView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        user = request.user
        if not user.check_password(str(request.data.get("password", ""))):
            return Response({"password": ["Password is incorrect."]}, status=status.HTTP_400_BAD_REQUEST)
        if user.totp_enabled:
            code = str(request.data.get("code", ""))
            if not (totp.verify_code(user, code) or totp.use_recovery_code(user, code)):
                return Response({"code": ["Enter a valid two-factor code."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cancel_for_account_deletion(user)  # stop Stripe billing first
        except Exception:  # noqa: BLE001
            security_log.exception("account_delete_billing_failed", extra={"event": "account_delete_billing_failed", "user_id": user.pk})
            return Response(
                {"detail": "We couldn't cancel your subscription. Nothing was deleted; try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        user_id, avatar_id = user.pk, user.avatar_id
        with transaction.atomic():
            # Cascades to workouts, posts, likes, comments, friendships, notifications...
            # Post photos are removed by the post_delete signal once unused.
            user.delete()
        if avatar_id:
            delete_photo_if_unused(avatar_id)
        logout(request)
        security_log.info("account_deleted", extra={"event": "account_deleted", "user_id": user_id})
        return Response(status=status.HTTP_204_NO_CONTENT)
