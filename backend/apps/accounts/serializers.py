import re

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.core.signing import photo_urls

from .models import User

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.]{3,30}$")


def check_password_strength(password, user, field="password"):
    """Run Django's password validators and report errors on the given field."""
    try:
        password_validation.validate_password(password, user)
    except DjangoValidationError as exc:
        raise serializers.ValidationError({field: list(exc.messages)})


class MeSerializer(serializers.ModelSerializer):
    """The logged-in user's own account, including private settings."""

    avatar = serializers.SerializerMethodField()
    is_premium = serializers.BooleanField(read_only=True)
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "bio",
            "avatar",
            "is_public",
            "units",
            "show_on_leaderboards",
            "totp_enabled",
            "is_premium",
            "subscription",
            "date_joined",
        ]
        read_only_fields = ["id", "username", "email", "totp_enabled", "date_joined"]

    def get_avatar(self, user):
        return photo_urls(user.avatar)

    def get_subscription(self, user):
        subscription = getattr(user, "subscription", None)
        if subscription is None:
            return None
        return {
            "plan": subscription.plan,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
        }


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal public info, safe to show to anyone (e.g. post authors, search results)."""

    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "is_public"]

    def get_avatar(self, user):
        urls = photo_urls(user.avatar)
        return urls["thumb"] if urls else None


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=30)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    is_public = serializers.BooleanField(default=False)
    units = serializers.ChoiceField(choices=User.Units.choices, default=User.Units.KG)

    def validate_username(self, value):
        if not USERNAME_RE.match(value):
            raise serializers.ValidationError(
                "Use 3-30 characters: letters, numbers, underscores and dots."
            )
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is taken.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        candidate = User(username=attrs["username"], email=attrs["email"])
        check_password_strength(attrs["password"], candidate)
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="Username or email")
    password = serializers.CharField(trim_whitespace=False)


class MeUpdateSerializer(serializers.ModelSerializer):
    current_password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)

    class Meta:
        model = User
        fields = ["email", "bio", "is_public", "units", "show_on_leaderboards", "current_password"]

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate(self, attrs):
        # Changing the email changes where password resets go, so require the password.
        if "email" in attrs and attrs["email"] != self.instance.email:
            if not self.instance.check_password(attrs.get("current_password", "")):
                raise serializers.ValidationError({"current_password": "Enter your current password."})
        attrs.pop("current_password", None)
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})
        check_password_strength(attrs["new_password"], user, field="new_password")
        return attrs
