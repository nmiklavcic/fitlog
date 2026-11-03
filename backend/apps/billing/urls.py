from django.urls import path

from . import views

urlpatterns = [
    path("status/", views.BillingStatusView.as_view(), name="billing-status"),
    path("checkout/", views.CheckoutView.as_view(), name="billing-checkout"),
    path("portal/", views.PortalView.as_view(), name="billing-portal"),
    path("cancel-demo/", views.CancelDemoView.as_view(), name="billing-cancel-demo"),
]
