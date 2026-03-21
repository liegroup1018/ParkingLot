"""
Track 2 — Core Inventory Models

ParkingSpot: physical spots in the lot (size, status).
LotOccupancy: ONE row per spot-size, the OCC sentinel table.

OCC (Optimistic Concurrency Control) pattern
============================================
Entry flow (reserve):
  1. SELECT spot_size, current_count, total_capacity, version
     FROM inventory_lot_occupancy
     WHERE spot_size = 'REGULAR'
  2. Guard: current_count < total_capacity → space available.
  3. UPDATE inventory_lot_occupancy
        SET current_count = current_count + 1,
            version       = version + 1
      WHERE spot_size = 'REGULAR'
        AND version   = <read_version>
        AND current_count < total_capacity   -- double-guard
  4. rows_affected == 0 → conflict, retry from step 1.
  5. rows_affected == 1 → success, issue ticket.

Exit flow (release):
  Same pattern but subtract 1 (with GREATEST guard to never go below 0).
"""
from django.db import models


# ──────────────────────────────────────────────────────────────────
# Shared enumerations (used by both models and tickets in Track 3)
# ──────────────────────────────────────────────────────────────────

class SpotSizeType(models.TextChoices):
    """Physical spot size — determines which vehicles may park here."""
    COMPACT   = "COMPACT",   "Compact"
    REGULAR   = "REGULAR",   "Regular"
    OVERSIZED = "OVERSIZED", "Oversized"


class VehicleType(models.TextChoices):
    """Vehicle classes recognised by the entry gate."""
    MOTORCYCLE = "MOTORCYCLE", "Motorcycle"
    CAR        = "CAR",        "Car"
    TRUCK      = "TRUCK",      "Truck"


# Vehicle → ordered list of spot sizes to try (overflow priority)
# Motorcycle: Compact → Regular → Oversized
# Car:        Regular → Oversized  (no Compact)
# Truck:      Oversized only
VEHICLE_SPOT_PRIORITY: dict[str, list[str]] = {
    VehicleType.MOTORCYCLE: [
        SpotSizeType.COMPACT,
        SpotSizeType.REGULAR,
        SpotSizeType.OVERSIZED,
    ],
    VehicleType.CAR: [
        SpotSizeType.REGULAR,
        SpotSizeType.OVERSIZED,
    ],
    VehicleType.TRUCK: [
        SpotSizeType.OVERSIZED,
    ],
}


class SpotStatus(models.TextChoices):
    """Operational state of a physical parking spot."""
    ACTIVE      = "ACTIVE",      "Active"
    MAINTENANCE = "MAINTENANCE", "Maintenance"


# ──────────────────────────────────────────────────────────────────
# Task 2.1 — ParkingSpot
# ──────────────────────────────────────────────────────────────────

class ParkingSpot(models.Model):
    """
    Represents one physical parking space in the lot.

    Indexes
    -------
    * ``(size_type, status)`` — most common filter: "how many COMPACT
      ACTIVE spots are there?" avoids a full-table scan.
    * ``status`` alone — listing all MAINTENANCE spots.
    """
    spot_number = models.CharField(
        max_length=20,
        unique=True,
        help_text='Human-readable identifier, e.g. "A-001" or "COMPACT-0001".',
    )
    size_type = models.CharField(
        max_length=10,
        choices=SpotSizeType.choices,
        db_index=True,
    )
    status = models.CharField(
        max_length=15,
        choices=SpotStatus.choices,
        default=SpotStatus.ACTIVE,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_parking_spots"
        ordering = ["spot_number"]
        indexes = [
            # Composite: availability queries (size + status)
            models.Index(
                fields=["size_type", "status"],
                name="idx_spots_size_status",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(size_type__in=SpotSizeType.values),
                name="chk_spot_size_type_valid",
            ),
            models.CheckConstraint(
                check=models.Q(status__in=SpotStatus.values),
                name="chk_spot_status_valid",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.spot_number} ({self.size_type}, {self.status})"


# ──────────────────────────────────────────────────────────────────
# Task 2.2 — LotOccupancy (OCC sentinel)
# ──────────────────────────────────────────────────────────────────

class LotOccupancy(models.Model):
    """
    One row per SpotSizeType. Acts as the fast-path counter table.

    The ``version`` column implements Optimistic Concurrency Control —
    every successful reserve/release increments it, so a stale writer
    always gets 0 affected rows and retries.

    OCC helpers
    -----------
    ``attempt_reserve(spot_size)``  — atomic increment (entry).
    ``attempt_release(spot_size)``  — atomic decrement (exit).
    ``available_size_for_vehicle(vehicle_type)`` — finds first size
        with remaining capacity following the overflow priority table.

    These are *class methods* so Track 3 can call them without
    instantiating a row object.
    """
    spot_size = models.CharField(
        max_length=10,
        choices=SpotSizeType.choices,
        unique=True,            # One row per size — enforced at DB level
        db_index=True,
    )
    total_capacity = models.PositiveIntegerField(
        default=0,
        help_text="Number of ACTIVE physical spots of this size.",
    )
    current_count = models.PositiveIntegerField(
        default=0,
        help_text="How many spots are currently occupied.",
    )
    version = models.PositiveBigIntegerField(
        default=0,
        help_text="OCC version — incremented on every reserve/release.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "inventory_lot_occupancy"
        ordering = ["spot_size"]
        constraints = [
            models.CheckConstraint(
                check=models.Q(spot_size__in=SpotSizeType.values),
                name="chk_occupancy_size_valid",
            ),
            models.CheckConstraint(
                check=models.Q(current_count__lte=models.F("total_capacity")),
                name="chk_occupancy_count_lte_capacity",
            ),
        ]

    def __str__(self) -> str:
        return (
            f"{self.spot_size}: {self.current_count}/{self.total_capacity}"
            f" (v{self.version})"
        )

    # ── OCC helpers ──────────────────────────────────────────────

    @classmethod
    def attempt_reserve(cls, spot_size: str) -> bool:
        """
        Atomically increment ``current_count`` for *spot_size*.

        Returns ``True`` on success, ``False`` if the lot is full or
        a concurrent writer updated the row between our READ and UPDATE
        (i.e., 0 rows affected — the OCC conflict case).

        The caller (gate entry view in Track 3) should retry up to
        MAX_RETRIES times on ``False``.
        """
        try:
            row = cls.objects.get(spot_size=spot_size)
        except cls.DoesNotExist:
            return False

        if row.current_count >= row.total_capacity:
            return False  # Lot section full — skip before hitting DB

        # Atomic Compare-And-Swap update:
        # WHERE version = <read_version> AND current_count < total_capacity
        # guarantees we never exceed capacity even under race conditions.
        updated = cls.objects.filter(
            spot_size=spot_size,
            version=row.version,
            current_count__lt=models.F("total_capacity"),
        ).update(
            current_count=models.F("current_count") + 1,
            version=models.F("version") + 1,
        )
        return updated == 1

    @classmethod
    def attempt_release(cls, spot_size: str) -> bool:
        """
        Atomically decrement ``current_count`` for *spot_size* (exit).

        Uses ``GREATEST(current_count - 1, 0)`` guard via a positional
        filter (``current_count__gt=0``) to prevent going below zero.
        Returns ``True`` on success.
        """
        try:
            row = cls.objects.get(spot_size=spot_size)
        except cls.DoesNotExist:
            return False

        if row.current_count <= 0:
            return False  # Already at 0 — nothing to release

        updated = cls.objects.filter(
            spot_size=spot_size,
            version=row.version,
            current_count__gt=0,
        ).update(
            current_count=models.F("current_count") - 1,
            version=models.F("version") + 1,
        )
        return updated == 1

    @classmethod
    def available_size_for_vehicle(cls, vehicle_type: str) -> str | None:
        """
        Return the first spot size from the vehicle's overflow priority
        list that still has remaining capacity, or ``None`` if the lot is
        completely full for that vehicle class.

        Used by the gate entry view (Track 3) to determine which size
        to OCC-reserve.

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
            for row in cls.objects.filter(spot_size__in=priority_list)
        }

        for size in priority_list:
            row = rows.get(size)
            if row and row.current_count < row.total_capacity:
                return size

        return None  # Lot full for this vehicle type
