"""
Custom manager for AuditLog.

Provides a convenience helper that other apps can use to write audit
entries without coupling themselves to the model import directly,
and enforces the "append-only" semantics of the table.
"""
import logging

from django.contrib.auth.models import UserManager
from django.db import models

logger = logging.getLogger(__name__)


class AuditLogManager(models.Manager):
    """Append-only manager for AuditLog entries."""

    def log_action(
        self,
        *,
        action_type: str,
        user=None,
        details: dict | None = None,
        ip_address: str | None = None,
    ):
        """
        Create a single AuditLog entry.

        Parameters
        ----------
        action_type : str
            One of the values from ``AuditActionType``.
        user : User | None
            The User who triggered the action.  Pass None for system events.
        details : dict | None
            Arbitrary JSON payload (old/new values, reason, etc.).
        ip_address : str | None
            IPv4 or IPv6 address of the requesting client.

        Returns
        -------
        AuditLog
            The newly created log entry.
        """
        entry = self.model(
            user=user,
            action_type=action_type,
            details=details or {},
            ip_address=ip_address,
        )
        entry.save(using=self._db)
        logger.info(
            "AuditLog created: action=%s user=%s",
            action_type,
            user.username if user else "system",
        )
        return entry

class CustomUserManager(UserManager):
    """
    Custom manager for the User model to handle superuser creation correctly.
    """
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        from apps.accounts.models import UserRole
        
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.ADMIN)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(username, email, password, **extra_fields)
