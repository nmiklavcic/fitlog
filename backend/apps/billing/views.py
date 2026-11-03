import logging

import stripe
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.metrics import CHECKOUTS_STARTED

from . import services
from .models import Subscription

logger = logging.getLogger("liftlog.billing")


def status_payload(user):
    subscription = Subscription.objects.filter(user=user).first()
    return {
        "mode": "stripe" if services.stripe_enabled() else "demo",
        "is_premium": user.is_premium,
        "subscription": None
        if subscription is None
        else {
            "plan": subscription.plan,
            "status": subscription.status,
            "current_period_end": subscription.current_period_end,
            "cancel_at_period_end": subscription.cancel_at_period_end,
            "manageable": bool(subscription.stripe_customer_id),
        },
        "prices": {
            plan: {"amount": info["amount"] / 100, "currency": services.CURRENCY, "interval": info["interval"]}
            for plan, info in services.PLANS.items()
        },
    }


def stripe_unavailable(exc):
    logger.error("stripe_error", extra={"event": "stripe_error", "error": str(exc)})
    return Response({"detail": "Payments are temporarily unavailable. Try again later."}, status=status.HTTP_502_BAD_GATEWAY)


class BillingStatusView(APIView):
    def get(self, request):
        session_id = request.query_params.get("session_id")
        if session_id and services.stripe_enabled():
            try:
                services.sync_checkout_session(request.user, session_id)
            except stripe.StripeError as exc:
                return stripe_unavailable(exc)
            request.user.refresh_from_db()  # also drops the cached subscription relation
        return Response(status_payload(request.user))


class CheckoutView(APIView):
    def post(self, request):
        plan = request.data.get("plan")
        if plan not in services.PLANS:
            return Response({"plan": ["Choose monthly or yearly."]}, status=status.HTTP_400_BAD_REQUEST)
        if request.user.is_premium:
            return Response({"detail": "You already have Premium."}, status=status.HTTP_409_CONFLICT)
        try:
            url = services.start_checkout(request.user, plan)
        except (stripe.StripeError, RuntimeError) as exc:
            return stripe_unavailable(exc)
        CHECKOUTS_STARTED.labels(plan).inc()
        return Response({"url": url})


class PortalView(APIView):
    """Stripe's Customer Portal: change plan, update card, cancel, download invoices."""

    def post(self, request):
        if not services.stripe_enabled():
            return Response({"detail": "Demo mode has no billing portal."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            url = services.portal_url(request.user)
        except stripe.StripeError as exc:
            return stripe_unavailable(exc)
        if not url:
            return Response({"detail": "No billing account yet."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"url": url})


class CancelDemoView(APIView):
    """Demo mode only: end the demo subscription immediately."""

    def post(self, request):
        subscription = Subscription.objects.filter(user=request.user, plan=Subscription.Plan.DEMO).first()
        if subscription is None:
            return Response({"detail": "No demo subscription."}, status=status.HTTP_400_BAD_REQUEST)
        subscription.status = Subscription.Status.CANCELED
        subscription.save(update_fields=["status", "updated_at"])
        return Response(status_payload(request.user))
