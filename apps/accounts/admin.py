"""
Django Admin configuration for the accounts app.

Provides a hardened, production-ready Admin interface:
  - User list with role/status filters
  - Audit logs displayed inline on the User change page
  - AuditLog admin is fully read-only (no add/edit/delete)
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import AuditLog, User


# ---------------------------------------------------------------------------
# Inline: Recent audit logs on the user detail page
# ---------------------------------------------------------------------------
class AuditLogInline(admin.TabularInline):
    model = AuditLog
    fk_name = "user"
    extra = 0
    max_num = 20
    can_delete = False
    readonly_fields = ("action_type", "details", "ip_address", "timestamp")
    fields = ("timestamp", "action_type", "ip_address", "details")
    ordering = ("-timestamp",)
    verbose_name = "Recent Audit Entry"
    verbose_name_plural = "Recent Audit Entries (last 20)"

    def has_add_permission(self, request, obj=None) -> bool:
        return False


# ---------------------------------------------------------------------------
# User Admin
# ---------------------------------------------------------------------------
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Extended Django admin for the custom User model.
    Adds the `role` and `two_factor_secret` fields to the standard fieldsets.
    """

    list_display = (
        "username",
        "email",
        "role",
        "is_active",
        "has_2fa_configured",
        "date_joined",
        "last_login",
    )
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")
    ordering = ("username",)

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            _("Personal info"),
            {"fields": ("first_name", "last_name", "email")},
        ),
        (
            _("RBAC & Security"),
            {
                "fields": ("role", "two_factor_secret"),
                "description": _(
                    "Set the user's role.  "
                    "Two-factor secret is managed via the API (/api/v1/auth/2fa/)."
                ),
            },
        ),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (
            _("Important dates"),
            {"fields": ("last_login", "date_joined")},
        ),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "role", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ("date_joined", "last_login")
    inlines = [AuditLogInline]

    # Prevent deletions from Django admin — deactivate instead.
    def has_delete_permission(self, request, obj=None) -> bool:
        return False


# ---------------------------------------------------------------------------
# AuditLog Admin (read-only)
# ---------------------------------------------------------------------------
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """
    Read-only admin interface for the AuditLog table.
    Supports date-hierarchy navigation and action-type filtering.
    """

    list_display = ("timestamp", "user", "action_type", "ip_address")
    list_filter = ("action_type",)
    search_fields = ("user__username", "action_type", "ip_address")
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)
    readonly_fields = ("user", "action_type", "details", "ip_address", "timestamp")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
