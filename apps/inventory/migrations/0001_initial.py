"""
Track 2 — Initial migration

Creates:
  inventory_parking_spots   (Task 2.1)
  inventory_lot_occupancy   (Task 2.2)

Indexes
-------
* idx_spots_size_status   — composite (size_type, status) for availability
                            queries ("how many COMPACT ACTIVE spots?").
* inventory_lot_occupancy.spot_size is UNIQUE (one row per size type).
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        # ── ParkingSpots ──────────────────────────────────────────
        migrations.CreateModel(
            name="ParkingSpot",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "spot_number",
                    models.CharField(
                        max_length=20,
                        unique=True,
                        help_text='Human-readable identifier, e.g. "A-001".',
                    ),
                ),
                (
                    "size_type",
                    models.CharField(
                        max_length=10,
                        choices=[
                            ("COMPACT",   "Compact"),
                            ("REGULAR",   "Regular"),
                            ("OVERSIZED", "Oversized"),
                        ],
                        db_index=True,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=15,
                        choices=[
                            ("ACTIVE",      "Active"),
                            ("MAINTENANCE", "Maintenance"),
                        ],
                        default="ACTIVE",
                        db_index=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table":  "inventory_parking_spots",
                "ordering":  ["spot_number"],
            },
        ),
        # Composite index: size + status (most common availability filter)
        migrations.AddIndex(
            model_name="ParkingSpot",
            index=models.Index(
                fields=["size_type", "status"],
                name="idx_spots_size_status",
            ),
        ),
        # DB-level enum guard: size_type
        migrations.AddConstraint(
            model_name="ParkingSpot",
            constraint=models.CheckConstraint(
                check=models.Q(
                    size_type__in=["COMPACT", "REGULAR", "OVERSIZED"]
                ),
                name="chk_spot_size_type_valid",
            ),
        ),
        # DB-level enum guard: status
        migrations.AddConstraint(
            model_name="ParkingSpot",
            constraint=models.CheckConstraint(
                check=models.Q(status__in=["ACTIVE", "MAINTENANCE"]),
                name="chk_spot_status_valid",
            ),
        ),

        # ── LotOccupancy ─────────────────────────────────────────
        migrations.CreateModel(
            name="LotOccupancy",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "spot_size",
                    models.CharField(
                        max_length=10,
                        unique=True,
                        db_index=True,
                        choices=[
                            ("COMPACT",   "Compact"),
                            ("REGULAR",   "Regular"),
                            ("OVERSIZED", "Oversized"),
                        ],
                    ),
                ),
                (
                    "total_capacity",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Number of ACTIVE physical spots of this size.",
                    ),
                ),
                (
                    "current_count",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="How many spots are currently occupied.",
                    ),
                ),
                (
                    "version",
                    models.PositiveBigIntegerField(
                        default=0,
                        help_text="OCC version — incremented on every reserve/release.",
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "inventory_lot_occupancy",
                "ordering": ["spot_size"],
            },
        ),
        # DB-level enum guard: spot_size
        migrations.AddConstraint(
            model_name="LotOccupancy",
            constraint=models.CheckConstraint(
                check=models.Q(
                    spot_size__in=["COMPACT", "REGULAR", "OVERSIZED"]
                ),
                name="chk_occupancy_size_valid",
            ),
        ),
        # DB-level guard: current_count ≤ total_capacity
        migrations.AddConstraint(
            model_name="LotOccupancy",
            constraint=models.CheckConstraint(
                check=models.Q(current_count__lte=models.F("total_capacity")),
                name="chk_occupancy_count_lte_capacity",
            ),
        ),
    ]
