"""
Track 2 — Django Admin for Inventory

ParkingSpot: list/filter/search, bulk status toggle.
LotOccupancy: fully read-only — no manual edits allowed
              (all mutations via OCC helpers or management command).
"""
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import LotOccupancy, ParkingSpot, SpotStatus


@admin.register(ParkingSpot)
class ParkingSpotAdmin(admin.ModelAdmin):
    list_display  = ("spot_number", "size_type", "status", "created_at", "updated_at")
    list_filter   = ("size_type", "status")
    search_fields = ("spot_number",)
    ordering      = ("size_type", "spot_number")
    readonly_fields = ("created_at", "updated_at")

    # Bulk actions in the admin changelist
    actions = ["mark_active", "mark_maintenance"]

    @admin.action(description="Mark selected spots as ACTIVE")
    def mark_active(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(status=SpotStatus.ACTIVE)
        self.message_user(request, f"{updated} spot(s) marked as ACTIVE.")

    @admin.action(description="Mark selected spots as MAINTENANCE")
    def mark_maintenance(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.update(status=SpotStatus.MAINTENANCE)
        self.message_user(
            request, f"{updated} spot(s) marked as MAINTENANCE.", level="WARNING"
        )


@admin.register(LotOccupancy)
class LotOccupancyAdmin(admin.ModelAdmin):
    """
    Read-only admin for the OCC table.
    Humans must not alter current_count / version manually.
    Use the management command or the OCC helpers instead.
    """
    list_display = (
        "spot_size",
        "total_capacity",
        "current_count",
        "available",
        "version",
        "updated_at",
    )
    ordering     = ("spot_size",)

    # No add / edit / delete through admin
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj=None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj=None
    ) -> bool:
        return False

    @admin.display(description="Available")
    def available(self, obj: LotOccupancy) -> int:
        return max(0, obj.total_capacity - obj.current_count)
