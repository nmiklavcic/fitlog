from datetime import timedelta

from django.conf import settings
from django.db import models

PAST_DUE_GRACE = timedelta(days=3)


class Subscription(models.Model):
    """The user's Premium status, kept in sync with Stripe by webhooks.

    One row per user that ever started a checkout (it also remembers their
    Stripe customer ID). In demo billing mode, rows have plan="demo" and
    simply expire at current_period_end.
    """

    class Plan(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly"
        DEMO = "demo", "Demo"

    class Status(models.TextChoices):
        # Mirrors Stripe's subscription statuses.
        INCOMPLETE = "incomplete", "Incomplete"
        INCOMPLETE_EXPIRED = "incomplete_expired", "Incomplete (expired)"
        TRIALING = "trialing", "Trialing"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        UNPAID = "unpaid", "Unpaid"
        PAUSED = "paused", "Paused"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="subscription")
    plan = models.CharField(max_length=10, choices=Plan.choices, default=Plan.MONTHLY)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INCOMPLETE)
    stripe_customer_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True, db_index=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} {self.plan} {self.status}"

    def grants_premium(self, now):
        if self.plan == self.Plan.DEMO:
            return self.status == self.Status.ACTIVE and bool(self.current_period_end and self.current_period_end > now)
        if self.status in (self.Status.ACTIVE, self.Status.TRIALING):
            return True  # Stripe tells us (by webhook) when this stops being true
        if self.status == self.Status.PAST_DUE:
            # Card failed: Stripe is retrying. Keep access for a few days meanwhile.
            return bool(self.current_period_end and now < self.current_period_end + PAST_DUE_GRACE)
        return False


class StripeEvent(models.Model):
    """Every processed webhook event ID. Stripe may deliver an event more than once;
    the unique constraint makes processing idempotent."""

    event_id = models.CharField(max_length=255, unique=True)
    type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type} {self.event_id}"
