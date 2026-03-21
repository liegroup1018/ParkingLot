"""
Accounts app configuration.
Track 1 / Task 1.1 — App structure.
"""
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """IAM & Access Control app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"
    verbose_name = "Identity & Access Management"

    def ready(self) -> None:
        """Import signals when the app is fully loaded."""
        import apps.accounts.signals  # noqa: F401
