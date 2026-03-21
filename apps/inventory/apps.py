"""
AppConfig for the inventory application.
Registers the app under its dotted path so Django's
app registry resolves it correctly.
"""
from django.apps import AppConfig


class InventoryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.inventory"
    verbose_name = "Inventory"
