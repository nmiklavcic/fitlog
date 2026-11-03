"""Everything that talks to Stripe, plus the demo-billing fallback.

Flow (Stripe mode):
1. POST /api/billing/checkout -> we create a Checkout Session and the browser
   goes to Stripe's hosted payment page (card data never touches our server).
2. Stripe redirects back to /premium/success?session_id=...; the frontend asks
   /api/billing/status?session_id=..., and we fetch the session from Stripe to
   sync right away (a redirect alone proves nothing, anyone can type that URL).
3. Stripe also sends signed webhooks (checkout.session.completed,
   customer.subscription.updated/deleted, invoice.payment_failed), which keep
   the Subscription row correct for renewals, cancellations and failed cards.
"""
import logging
from datetime import datetime, timedelta, timezone as dt_timezone

import stripe
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User

from .models import Subscription

logger = logging.getLogger("liftlog.billing")

PLANS = {
    "monthly": {"lookup_key": "liftlog_premium_monthly", "amount": 499, "interval": "month"},
    "yearly": {"lookup_key": "liftlog_premium_yearly", "amount": 3999, "interval": "year"},
}
CURRENCY = "eur"
PRODUCT_NAME = "Liftlog Premium"
DEMO_DAYS = 30


def stripe_enabled():
    return bool(settings.STRIPE_SECRET_KEY)


def client():
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY)


def price_id(plan):
    """Look the price up by its lookup key (set by `manage.py setup_stripe`); cached for an hour."""
    key = f"stripe-price:{plan}"
    cached = cache.get(key)
    if cached:
        return cached
    prices = client().v1.prices.list(params={"lookup_keys": [PLANS[plan]["lookup_key"]], "active": True, "limit": 1})
    if not prices.data:
        raise RuntimeError(f"No Stripe price with lookup key {PLANS[plan]['lookup_key']}; run `manage.py setup_stripe`.")
    cache.set(key, prices.data[0].id, 60 * 60)
    return prices.data[0].id


def _subscription_row(user):
    subscription, _ = Subscription.objects.get_or_create(user=user)
    return subscription


def ensure_customer(user):
    subscription = _subscription_row(user)
    if not subscription.stripe_customer_id:
        customer = client().v1.customers.create(
            params={"email": user.email, "name": user.username, "metadata": {"user_id": str(user.pk)}}
        )
        subscription.stripe_customer_id = customer.id
        subscription.save(update_fields=["stripe_customer_id", "updated_at"])
    return subscription.stripe_customer_id


def start_checkout(user, plan):
    """Returns the URL the browser should go to."""
    if not stripe_enabled():
        return start_demo(user, plan)
    session = client().v1.checkout.sessions.create(
        params={
            "mode": "subscription",
            "customer": ensure_customer(user),
            "client_reference_id": str(user.pk),
            "line_items": [{"price": price_id(plan), "quantity": 1}],
            "success_url": f"{settings.PUBLIC_BASE_URL}/premium/success?session_id={{CHECKOUT_SESSION_ID}}",
            "cancel_url": f"{settings.PUBLIC_BASE_URL}/premium?canceled=1",
            "subscription_data": {"metadata": {"user_id": str(user.pk)}},
            "metadata": {"user_id": str(user.pk), "plan": plan},
        }
    )
    return session.url


def start_demo(user, plan):
    """Demo billing: no payment, Premium for 30 days. Used when no Stripe key is configured."""
    Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": Subscription.Plan.DEMO,
            "status": Subscription.Status.ACTIVE,
            "current_period_end": timezone.now() + timedelta(days=DEMO_DAYS),
            "cancel_at_period_end": False,
        },
    )
    logger.info("demo_subscription_started", extra={"event": "demo_subscription_started", "user_id": user.pk, "plan": plan})
    return "/premium/success?demo=1"  # stays inside the app (Stripe needs absolute URLs, we don't)


def portal_url(user):
    subscription = getattr(user, "subscription", None)
    if not subscription or not subscription.stripe_customer_id:
        return None
    session = client().v1.billing_portal.sessions.create(
        params={"customer": subscription.stripe_customer_id, "return_url": f"{settings.PUBLIC_BASE_URL}/settings"}
    )
    return session.url


def _timestamp(value):
    return datetime.fromtimestamp(value, tz=dt_timezone.utc) if value else None


def apply_subscription(data, user=None):
    """Copy a Stripe subscription (as a plain dict) onto our Subscription row."""
    rows = Subscription.objects.select_for_update()
    subscription = rows.filter(stripe_subscription_id=data["id"]).first() or rows.filter(
        stripe_customer_id=data.get("customer") or "-"
    ).first()
    if subscription is None:
        user_id = user.pk if user else (data.get("metadata") or {}).get("user_id")
        target = User.objects.filter(pk=user_id).first() if user_id else None
        if target is None:
            logger.warning("subscription_without_user", extra={"event": "subscription_without_user", "stripe_subscription": data["id"]})
            return None
        subscription = _subscription_row(target)

    items = (data.get("items") or {}).get("data") or []
    first_item = items[0] if items else {}
    price = first_item.get("price") or {}
    interval = (price.get("recurring") or {}).get("interval")

    subscription.stripe_subscription_id = data["id"]
    subscription.stripe_customer_id = data.get("customer") or subscription.stripe_customer_id
    subscription.status = data.get("status", subscription.status)
    subscription.plan = Subscription.Plan.YEARLY if interval == "year" else Subscription.Plan.MONTHLY
    # Since Stripe API 2025-03-31 the billing period lives on the subscription item.
    subscription.current_period_end = _timestamp(first_item.get("current_period_end") or data.get("current_period_end"))
    subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end") or data.get("cancel_at"))
    subscription.save()
    return subscription


@transaction.atomic
def sync_checkout_session(user, session_id):
    """Called when the user returns from Stripe Checkout."""
    session = client().v1.checkout.sessions.retrieve(session_id, params={"expand": ["subscription"]}).to_dict()
    if session.get("client_reference_id") != str(user.pk):
        return None  # someone else's session: ignore
    if isinstance(session.get("subscription"), dict):
        return apply_subscription(session["subscription"], user=user)
    return None


def cancel_for_account_deletion(user):
    """Stop billing before an account is deleted (raises if Stripe can't be reached)."""
    subscription = getattr(user, "subscription", None)
    if not subscription or not subscription.stripe_subscription_id or not stripe_enabled():
        return
    if subscription.status in (Subscription.Status.CANCELED, Subscription.Status.INCOMPLETE_EXPIRED):
        return
    client().v1.subscriptions.cancel(subscription.stripe_subscription_id)
    logger.info("subscription_canceled_for_deletion", extra={"event": "subscription_canceled_for_deletion", "user_id": user.pk})


def grant(user, days):
    """Manual Premium (management command / demos)."""
    return Subscription.objects.update_or_create(
        user=user,
        defaults={
            "plan": Subscription.Plan.DEMO,
            "status": Subscription.Status.ACTIVE,
            "current_period_end": timezone.now() + timedelta(days=days),
            "cancel_at_period_end": False,
        },
    )[0]
