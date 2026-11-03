from django.contrib import admin

from .models import StripeEvent, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["user", "plan", "status", "current_period_end", "cancel_at_period_end"]
    list_filter = ["plan", "status"]
    search_fields = ["user__username", "stripe_customer_id", "stripe_subscription_id"]


@admin.register(StripeEvent)
class StripeEventAdmin(admin.ModelAdmin):
    list_display = ["event_id", "type", "processed_at"]
    list_filter = ["type"]
