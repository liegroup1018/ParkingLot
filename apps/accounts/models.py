"""
Models for the Identity & Access Management (IAM) module.

Implements:
  - Task 1.3 : Custom User model (AbstractUser + role field + TOTP 2FA)
  - Task 1.5 : AuditLogs model with JSON `details` payload

Design Decisions
----------------
- We extend AbstractUser rather than AbstractBaseUser to keep Django's
  admin, permissions, and group machinery intact.  Only the `role` field
  and `two_factor_secret` are added.
- db_index is applied to every column that will appear in WHERE / JOIN
  clauses so MySQL can plan efficient queries.
- on_delete=SET_NULL for AuditLogs.user_id so audit history is never
  lost when a staff account is deleted.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers import AuditLogManager, CustomUserManager


# ---------------------------------------------------------------------------
# Choices
# ---------------------------------------------------------------------------
class UserRole(models.TextChoices):
    """RBAC roles supported by the system (PRD §4.2)."""

    ADMIN = "ADMIN", _("Management Admin")
    ATTENDANT = "ATTENDANT", _("Parking Attendant")


class AuditActionType(models.TextChoices):
    """Enumeration of all sensitive action types (PRD §4.2)."""

    MANUAL_GATE_OPEN = "MANUAL_GATE_OPEN", _("Manual Gate Open")
    PRICE_CHANGE = "PRICE_CHANGE", _("Price Rule Changed")
    SPOT_CREATED = "SPOT_CREATED", _("Parking Spot Created")
    SPOT_UPDATED = "SPOT_UPDATED", _("Parking Spot Updated")
    SPOT_DELETED = "SPOT_DELETED", _("Parking Spot Deleted")
    USER_CREATED = "USER_CREATED", _("User Account Created")
    USER_DEACTIVATED = "USER_DEACTIVATED", _("User Account Deactivated")
    LOGIN_SUCCESS = "LOGIN_SUCCESS", _("Successful Login")
    LOGIN_FAILED = "LOGIN_FAILED", _("Failed Login Attempt")
    LOGOUT = "LOGOUT", _("User Logout")
    PASSWORD_CHANGED = "PASSWORD_CHANGED", _("Password Changed")
    TICKET_VOIDED = "TICKET_VOIDED", _("Ticket Voided")
    OCCUPANCY_RESET = "OCCUPANCY_RESET", _("Lot Occupancy Reset")


# ---------------------------------------------------------------------------
# Custom User model (Task 1.3)
# ---------------------------------------------------------------------------
class User(AbstractUser):
    """
    Extended user model.

    Adds:
      role              — RBAC role (Admin / Attendant)
      two_factor_secret — TOTP secret stored per PRD §4.2
    """

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.ATTENDANT,
        db_index=True,                      # fast WHERE role = 'ADMIN' queries
        help_text=_("The RBAC role that controls which endpoints this user may access."),
    )
    two_factor_secret = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text=_(
            "TOTP base32 secret (pyotp). Empty string means 2FA is not yet configured. "
            "Only Admin accounts require 2FA per PRD §4.2."
        ),
    )

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        db_table = "accounts_users"         # explicit table name for readability
        indexes = [
            models.Index(fields=["role", "is_active"], name="idx_users_role_active"),
        ]

    # ------------------------------------------------------------------
    # Business helpers
    # ------------------------------------------------------------------
    @property
    def is_admin(self) -> bool:
        """True if this user has the Management Admin role."""
        return self.role == UserRole.ADMIN

    @property
    def is_attendant(self) -> bool:
        """True if this user has the Parking Attendant role."""
        return self.role == UserRole.ATTENDANT

    @property
    def has_2fa_configured(self) -> bool:
        """True when a TOTP secret has been provisioned."""
        return bool(self.two_factor_secret)

    def __str__(self) -> str:
        return f"{self.username} ({self.get_role_display()})"


# ---------------------------------------------------------------------------
# AuditLogs model (Task 1.5)
# ---------------------------------------------------------------------------
class AuditLog(models.Model):
    """
    Immutable audit trail entry.

    Every sensitive action in the system (gate override, price change, etc.)
    must produce one of these records.  The model is intentionally write-only
    — no ``update()`` or ``save()`` on existing rows should ever run.

    Performance notes
    -----------------
    - ``user`` FK has db_index=True (default for FK) but we add a composite
      index on (user, timestamp) for time-range queries per user.
    - ``action_type`` is indexed to support dashboard filters like
      "show only MANUAL_GATE_OPEN today".
    - ``timestamp`` uses ``db_index=True`` for ORDER BY and date-range scans.
    """

    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,          # preserve logs even if user deleted
        related_name="audit_logs",
        help_text=_("The user who initiated the action. NULL = system-generated."),
    )
    action_type = models.CharField(
        max_length=50,
        choices=AuditActionType.choices,
        db_index=True,                      # filter by action type efficiently
        help_text=_("Semantic code for the action that took place."),
    )
    details = models.JSONField(
        default=dict,
        help_text=_(
            "Arbitrary JSON payload describing the change "
            "(e.g. old vs new values for price changes)."
        ),
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text=_("Source IP address of the HTTP request, if available."),
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,                      # ORDER BY timestamp / date-range queries
        help_text=_("UTC timestamp when the action occurred. Set automatically."),
    )

    # Custom append-only manager
    objects = AuditLogManager()

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        db_table = "accounts_audit_logs"
        ordering = ["-timestamp"]
        indexes = [
            # Range scans per user over time (e.g. "all actions by admin A this week")
            models.Index(
                fields=["user", "-timestamp"],
                name="idx_audit_user_timestamp",
            ),
            # Filter all events of a specific type in a date window
            models.Index(
                fields=["action_type", "-timestamp"],
                name="idx_audit_type_timestamp",
            ),
        ]

    def __str__(self) -> str:
        username = self.user.username if self.user else "system"
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {username} — {self.action_type}"
