from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone


class UserManager(DjangoUserManager):
    def get_by_natural_key(self, username):
        # Log in with "Alice" or "alice": usernames are unique case-insensitively.
        return self.get(username__iexact=username)


class User(AbstractUser):
    class Units(models.TextChoices):
        KG = "kg", "Kilograms"
        LB = "lb", "Pounds"

    email = models.EmailField("email address")
    bio = models.CharField(max_length=300, blank=True)
    avatar = models.ForeignKey(
        "core.Photo", null=True, blank=True, on_delete=models.SET_NULL, related_name="avatar_of"
    )
    # Privacy by default: new accounts are private until the user opts in.
    is_public = models.BooleanField(default=False)
    units = models.CharField(max_length=2, choices=Units.choices, default=Units.KG)
    show_on_leaderboards = models.BooleanField(default=True)

    # Two-factor authentication (TOTP, RFC 6238).
    totp_secret = models.CharField(max_length=64, blank=True)
    totp_enabled = models.BooleanField(default=False)
    totp_last_step = models.BigIntegerField(null=True, blank=True)  # blocks code reuse
    recovery_codes = models.JSONField(default=list, blank=True)  # SHA-256 hashes, never plaintext

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("username"), name="user_username_ci_unique"),
            models.UniqueConstraint(Lower("email"), name="user_email_ci_unique"),
        ]

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    @property
    def is_premium(self):
        subscription = getattr(self, "subscription", None)
        return bool(subscription and subscription.grants_premium(timezone.now()))
