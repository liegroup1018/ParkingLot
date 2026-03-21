"""
Track 2 — Inventory Serializers

ParkingSpot serializers (create/read/update/bulk-seed)
LotOccupancy serializers (read-only OCC state)
"""
from django.db import transaction
from rest_framework import serializers

from .models import LotOccupancy, ParkingSpot, SpotSizeType, SpotStatus


# ──────────────────────────────────────────────────────────────────
# ParkingSpot
# ──────────────────────────────────────────────────────────────────

class ParkingSpotReadSerializer(serializers.ModelSerializer):
    """Safe read representation of a single parking spot."""

    class Meta:
        model = ParkingSpot
        fields = [
            "id",
            "spot_number",
            "size_type",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ParkingSpotCreateSerializer(serializers.ModelSerializer):
    """
    Create a single parking spot.
    spot_number is unique — validated at both serializer and DB level.
    """

    class Meta:
        model = ParkingSpot
        fields = ["spot_number", "size_type", "status"]
        extra_kwargs = {
            "status": {"default": SpotStatus.ACTIVE},
        }

    def validate_spot_number(self, value: str) -> str:
        return value.strip().upper()


class ParkingSpotUpdateSerializer(serializers.ModelSerializer):
    """
    Partial update — only ``status`` may change after creation.
    spot_number and size_type are immutable once set.
    """
    class Meta:
        model = ParkingSpot
        fields = ["status"]


# ──────────────────────────────────────────────────────────────────
# Bulk-seed endpoint (Task 2.3)
# ──────────────────────────────────────────────────────────────────

class BulkSpotSeedSerializer(serializers.Serializer):
    """
    Admin endpoint to seed the lot in one shot.

    Accepts three counts — the system auto-generates spot_numbers
    using the pattern  SIZE-NNNN  (e.g. ``COMPACT-0001``).
    Existing spots are **not** deleted; new ones are appended.

    Example body
    ------------
    .. code-block:: json

        {
            "compact_count":   3000,
            "regular_count":   5000,
            "oversized_count": 2000
        }
    """
    compact_count   = serializers.IntegerField(min_value=0, default=0)
    regular_count   = serializers.IntegerField(min_value=0, default=0)
    oversized_count = serializers.IntegerField(min_value=0, default=0)

    MAX_PER_SIZE = 10_000  # Hard cap per PRD §2.1

    def validate(self, attrs):
        total_requested = (
            attrs["compact_count"]
            + attrs["regular_count"]
            + attrs["oversized_count"]
        )
        if total_requested == 0:
            raise serializers.ValidationError(
                "At least one count must be greater than 0."
            )
        # Per-size guard
        for key, size in [
            ("compact_count",   SpotSizeType.COMPACT),
            ("regular_count",   SpotSizeType.REGULAR),
            ("oversized_count", SpotSizeType.OVERSIZED),
        ]:
            if attrs[key] > self.MAX_PER_SIZE:
                raise serializers.ValidationError(
                    {key: f"Cannot exceed {self.MAX_PER_SIZE} spots per size."}
                )
        return attrs

    @transaction.atomic
    def create_spots(self) -> dict:
        """
        Bulk-insert new spots, skipping any spot_number that already
        exists (``ignore_conflicts=True`` → idempotent).

        Returns a summary dict with created counts per size.
        """
        data = self.validated_data
        mapping = [
            (SpotSizeType.COMPACT,   data["compact_count"],   "COMPACT"),
            (SpotSizeType.REGULAR,   data["regular_count"],   "REGULAR"),
            (SpotSizeType.OVERSIZED, data["oversized_count"], "OVERSIZED"),
        ]
        summary = {}
        for size_type, count, prefix in mapping:
            if count == 0:
                summary[size_type.lower()] = 0
                continue

            # Find the current highest number for this prefix so we
            # continue from where we left off (idempotent re-runs).
            existing_max = (
                ParkingSpot.objects
                .filter(spot_number__startswith=f"{prefix}-")
                .count()
            )
            start = existing_max + 1

            spots = [
                ParkingSpot(
                    spot_number=f"{prefix}-{i:04d}",
                    size_type=size_type,
                    status=SpotStatus.ACTIVE,
                )
                for i in range(start, start + count)
            ]
            created = ParkingSpot.objects.bulk_create(
                spots,
                ignore_conflicts=True,  # Safe re-runs
            )
            summary[size_type.lower()] = len(created)

        return summary


# ──────────────────────────────────────────────────────────────────
# LotOccupancy (read-only API response)
# ──────────────────────────────────────────────────────────────────

class LotOccupancySerializer(serializers.ModelSerializer):
    """
    Read-only view of the OCC sentinel table.

    Adds a computed ``available`` field so clients don't have to
    subtract on their side.
    """
    available = serializers.SerializerMethodField()

    class Meta:
        model = LotOccupancy
        fields = [
            "spot_size",
            "total_capacity",
            "current_count",
            "available",
            "version",
            "updated_at",
        ]
        read_only_fields = fields

    def get_available(self, obj: LotOccupancy) -> int:
        return max(0, obj.total_capacity - obj.current_count)


# ──────────────────────────────────────────────────────────────────
# Summary response serializer (GET /api/v1/spots/summary/)
# ──────────────────────────────────────────────────────────────────

class SpotSummarySerializer(serializers.Serializer):
    """
    Aggregated counts returned by the summary endpoint.
    Not backed by a model — constructed in the view.
    """
    size_type   = serializers.ChoiceField(choices=SpotSizeType.choices)
    total       = serializers.IntegerField()
    active      = serializers.IntegerField()
    maintenance = serializers.IntegerField()
