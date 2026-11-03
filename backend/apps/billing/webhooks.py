import logging

import stripe
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.core.metrics import STRIPE_WEBHOOKS
from apps.social.models import Notification
from apps.social.services import notify

from . import services
from .models import StripeEvent, Subscription

logger = logging.getLogger("liftlog.billing")

SUBSCRIPTION_EVENTS = {
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
}


def handle_event(event_type, obj):
    if event_type == "checkout.session.completed":
        if obj.get("mode") == "subscription" and obj.get("subscription"):
            data = services.client().v1.subscriptions.retrieve(obj["subscription"]).to_dict()
            data.setdefault("metadata", {}).setdefault("user_id", obj.get("client_reference_id"))
            services.apply_subscription(data)
    elif event_type in SUBSCRIPTION_EVENTS:
        services.apply_subscription(obj)
    elif event_type == "invoice.payment_failed":
        subscription = Subscription.objects.filter(stripe_customer_id=obj.get("customer") or "-").select_related("user").first()
        if subscription:
            notify(subscription.user, Notification.Kind.PAYMENT_FAILED, data={"invoice": obj.get("id")})


@csrf_exempt  # Stripe can't send a CSRF token; the signature check below replaces it.
@require_POST
def stripe_webhook(request):
    """Stripe -> us. A plain Django view: no session, and we need the raw body for the signature."""
    if not services.stripe_enabled() or not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=404)
    try:
        # Verifies the HMAC signature and rejects events older than 5 minutes (replays).
        event = services.client().construct_event(
            request.body, request.headers.get("Stripe-Signature"), settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError):
        STRIPE_WEBHOOKS.labels("unknown", "bad_signature").inc()
        logger.warning("stripe_webhook_bad_signature", extra={"event": "stripe_webhook_bad_signature"})
        return HttpResponseBadRequest("Invalid signature")

    event_type = event.type
    try:
        with transaction.atomic():
            _, created = StripeEvent.objects.get_or_create(event_id=event.id, defaults={"type": event_type})
            if not created:
                STRIPE_WEBHOOKS.labels(event_type, "duplicate").inc()
                return JsonResponse({"received": True, "duplicate": True})
            handle_event(event_type, event.data.object.to_dict())
    except Exception:
        # Rolled back (including the StripeEvent row), so Stripe's retry gets processed.
        STRIPE_WEBHOOKS.labels(event_type, "error").inc()
        logger.exception("stripe_webhook_failed", extra={"event": "stripe_webhook_failed", "stripe_event": event.id})
        return HttpResponse(status=500)

    STRIPE_WEBHOOKS.labels(event_type, "ok").inc()
    logger.info("stripe_webhook", extra={"event": "stripe_webhook", "stripe_event": event.id, "type": event_type})
    return JsonResponse({"received": True})
