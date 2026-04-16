"""
Django signals for the accounts app.

Automatically creates an AuditLog entry when a User account is created.
Keeping the signal lightweight — heavy business logic belongs in services.
"""
import logging

from django.contrib.auth import user_logged_in, user_login_failed, user_logged_out
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="accounts.User")
def log_user_created(sender, instance, created: bool, **kwargs) -> None:
    """Write an audit log entry the first time a User is saved."""
    if not created:
        return
    # Import here to avoid circular imports at module load time
    from apps.accounts.models import AuditLog, AuditActionType  # noqa: PLC0415

    AuditLog.objects.log_action(
        action_type=AuditActionType.USER_CREATED,
        user=None,  # system action — no requesting user available in signal
        details={
            "username": instance.username,
            "role": instance.role,
            "email": instance.email,
        },
    )
    logger.info("New user created: %s (role=%s)", instance.username, instance.role)


@receiver(user_logged_in)
def log_login_success(sender, request, user, **kwargs) -> None:
    """Record a successful login event."""
    from apps.accounts.models import AuditLog, AuditActionType  # noqa: PLC0415

    ip = _get_client_ip(request)
    AuditLog.objects.log_action(
        action_type=AuditActionType.LOGIN_SUCCESS,
        user=user,
        details={"username": user.username},
        ip_address=ip,
    )


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs) -> None:
    """Record a failed login attempt (no user object available)."""
    from apps.accounts.models import AuditLog, AuditActionType  # noqa: PLC0415

    ip = _get_client_ip(request)
    AuditLog.objects.log_action(
        action_type=AuditActionType.LOGIN_FAILED,
        user=None,
        details={"attempted_username": credentials.get("username", "")},
        ip_address=ip,
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs) -> None:
    """Record a logout event."""
    from apps.accounts.models import AuditLog, AuditActionType  # noqa: PLC0415

    ip = _get_client_ip(request)
    AuditLog.objects.log_action(
        action_type=AuditActionType.LOGOUT,
        user=user,
        details={"username": getattr(user, "username", "")},
        ip_address=ip,
    )


def _get_client_ip(request) -> str | None:
    """Extract the client IP from the request, respecting proxy headers."""
    if request is None:
        return None
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
