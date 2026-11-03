from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ["username", "email", "is_public", "totp_enabled", "is_active", "is_staff", "date_joined"]
    list_filter = ["is_public", "totp_enabled", "is_active", "is_staff"]
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("Liftlog", {"fields": ["bio", "is_public", "units", "show_on_leaderboards", "totp_enabled"]}),
    )
    readonly_fields = ["totp_enabled"]
