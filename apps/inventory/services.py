"""
Inventory service layer

Isolates OCC retry and spot availability logic from the model layer.
"""
import logging
from typing import Optional
from django.db import models
from apps.inventory.models import LotOccupancy, VEHICLE_SPOT_PRIORITY

logger = logging.getLogger(__name__)

class InventoryService:
    """
    Service class for inventory-related operations.
    """

    @staticmethod
    def attempt_reserve(spot_size: str) -> bool:
        """
        Atomically increment ``current_count`` for *spot_size*.

        Returns ``True`` on success, ``False`` if the lot is full or
        a concurrent writer updated the row between our READ and UPDATE
        (i.e., 0 rows affected — the OCC conflict case).

        The caller should retry up to MAX_RETRIES times on ``False``.
        """
        try:
            row = LotOccupancy.objects.get(spot_size=spot_size)
        except LotOccupancy.DoesNotExist:
            return False

        if row.current_count >= row.total_capacity:
            return False  # Lot section full — skip before hitting DB

        # Atomic Compare-And-Swap update:
        # WHERE version = <read_version> AND current_count < total_capacity
        # guarantees we never exceed capacity even under race conditions.
        updated = LotOccupancy.objects.filter(
            spot_size=spot_size,
            version=row.version,
            current_count__lt=models.F("total_capacity"),
        ).update(
            current_count=models.F("current_count") + 1,
            version=models.F("version") + 1,
        )
        return updated == 1

    @staticmethod
    def attempt_release(spot_size: str) -> bool:
        """
        Atomically decrement ``current_count`` for *spot_size* (exit).

        Uses ``GREATEST(current_count - 1, 0)`` guard via a positional
        filter (``current_count__gt=0``) to prevent going below zero.
        Returns ``True`` on success.
        """
        try:
            row = LotOccupancy.objects.get(spot_size=spot_size)
        except LotOccupancy.DoesNotExist:
            return False

        if row.current_count <= 0:
            return False  # Already at 0 — nothing to release

        updated = LotOccupancy.objects.filter(
            spot_size=spot_size,
            version=row.version,
            current_count__gt=0,
        ).update(
            current_count=models.F("current_count") - 1,
            version=models.F("version") + 1,
        )
        return updated == 1

    @staticmethod
    def available_size_for_vehicle(vehicle_type: str) -> Optional[str]:
        """
        Return the first spot size from the vehicle's overflow priority
        list that still has remaining capacity, or ``None`` if the lot is
        completely full for that vehicle class.

        Overflow priority (from PRD §3.1):
          Motorcycle → COMPACT → REGULAR → OVERSIZED
          Car        → REGULAR → OVERSIZED
          Truck      → OVERSIZED
        """
        priority_list = VEHICLE_SPOT_PRIORITY.get(vehicle_type, [])
        if not priority_list:
            return None

        # Fetch all relevant rows in a single query, keyed by spot_size
        rows = {
            row.spot_size: row
            for row in LotOccupancy.objects.filter(spot_size__in=priority_list)
        }

        for size in priority_list:
            row = rows.get(size)
            if row and row.current_count < row.total_capacity:
                return size

        return None  # Lot full for this vehicle type
