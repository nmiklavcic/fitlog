from django.urls import path

from . import views

urlpatterns = [
    path("csrf/", views.CsrfView.as_view(), name="auth-csrf"),
    path("register/", views.RegisterView.as_view(), name="auth-register"),
    path("login/", views.LoginView.as_view(), name="auth-login"),
    path("logout/", views.LogoutView.as_view(), name="auth-logout"),
    path("me/", views.MeView.as_view(), name="auth-me"),
    path("me/avatar/", views.MeAvatarView.as_view(), name="auth-me-avatar"),
    path("me/export/", views.ExportView.as_view(), name="auth-me-export"),
    path("me/delete/", views.DeleteAccountView.as_view(), name="auth-me-delete"),
    path("password/change/", views.PasswordChangeView.as_view(), name="auth-password-change"),
    path("password/reset/", views.PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path("password/reset/confirm/", views.PasswordResetConfirmView.as_view(), name="auth-password-reset-confirm"),
    path("login/2fa/", views.LoginTwoFactorView.as_view(), name="auth-login-2fa"),
    path("2fa/setup/", views.TwoFactorSetupView.as_view(), name="auth-2fa-setup"),
    path("2fa/confirm/", views.TwoFactorConfirmView.as_view(), name="auth-2fa-confirm"),
    path("2fa/disable/", views.TwoFactorDisableView.as_view(), name="auth-2fa-disable"),
]
