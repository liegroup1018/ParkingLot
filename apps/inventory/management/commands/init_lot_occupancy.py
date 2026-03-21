"""
Track 2 — Task 2.4: Management command to initialise / sync LotOccupancy.

Usage
-----
    python manage.py init_lot_occupancy
    python manage.py init_lot_occupancy --reset       # zero current_count too

What it does
------------
1. Counts ACTIVE ParkingSpots grouped by size_type.
2. For each SpotSizeType, upserts a LotOccupancy row:
   * Sets total_capacity  = count of ACTIVE spots.
   * Sets current_count   = 0   (unless --keep-counts is passed).
   * Sets version         = 0   (unless --keep-counts is passed).
3. Prints a summary table.

This command is idempotent — run it any time you add/remove bulk spots
and want to resync the capacity counter without touching live counts
(use --keep-counts to preserve current_count and version).
"""
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.inventory.models import LotOccupancy, ParkingSpot, SpotSizeType, SpotStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Initialise or resync the LotOccupancy table from ParkingSpots data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--keep-counts",
            action="store_true",
            default=False,
            help=(
                "If set, only total_capacity is updated; "
                "current_count and version are left unchanged. "
                "Useful for live resync without disrupting in-flight reservations."
            ),
        )

    def handle(self, *args, **options):
        keep_counts = options["keep_counts"]

        self.stdout.write(self.style.MIGRATE_HEADING(
            "\nInitialising LotOccupancy table…"
        ))

        # Aggregate: ACTIVE spots per size_type (one DB query)
        active_counts: dict[str, int] = {
            row["size_type"]: row["cnt"]
            for row in (
                ParkingSpot.objects
                .filter(status=SpotStatus.ACTIVE)
                .values("size_type")
                .annotate(cnt=Count("id"))
            )
        }

        rows_created = 0
        rows_updated = 0

        with transaction.atomic():
            for size in SpotSizeType.values:
                capacity = active_counts.get(size, 0)

                defaults: dict = {"total_capacity": capacity}
                if not keep_counts:
                    defaults["current_count"] = 0
                    defaults["version"] = 0

                _, created = LotOccupancy.objects.update_or_create(
                    spot_size=size,
                    defaults=defaults,
                )
                if created:
                    rows_created += 1
                else:
                    rows_updated += 1

        # Summary output
        self.stdout.write("")
        self.stdout.write(
            f"{'SIZE':<12}  {'TOTAL':<8}  {'CURRENT':<10}  {'VERSION'}"
        )
        self.stdout.write("-" * 45)
        for row in LotOccupancy.objects.order_by("spot_size"):
            self.stdout.write(
                f"{row.spot_size:<12}  "
                f"{row.total_capacity:<8}  "
                f"{row.current_count:<10}  "
                f"{row.version}"
            )
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done — {rows_created} row(s) created, {rows_updated} row(s) updated."
        ))
        if keep_counts:
            self.stdout.write(
                self.style.WARNING(
                    "  Note: --keep-counts was set; current_count and version "
                    "were NOT reset."
                )
            )

        logger.info(
            "init_lot_occupancy: created=%d updated=%d keep_counts=%s",
            rows_created,
            rows_updated,
            keep_counts,
        )
