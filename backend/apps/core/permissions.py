from rest_framework import permissions, status
from rest_framework.exceptions import APIException


class PremiumRequired(APIException):
    """HTTP 402 Payment Required: the feature exists, but needs a Premium subscription."""

    status_code = status.HTTP_402_PAYMENT_REQUIRED
    default_detail = "This feature is part of Liftlog Premium."
    default_code = "premium_required"

    def __init__(self, detail=None):
        # A dict detail is returned as-is: {"detail": "...", "code": "premium_required"},
        # so the frontend can show the upgrade prompt instead of a generic error.
        super().__init__({"detail": detail or self.default_detail, "code": self.default_code})


def require_premium(user):
    if not user.is_premium:
        raise PremiumRequired()


class IsPremium(permissions.BasePermission):
    """Server-side gate for Premium endpoints. The UI hides them too, but this is what enforces it."""

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            require_premium(request.user)
        return True
