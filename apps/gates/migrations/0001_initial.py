"""
Track 3 — Initial migration

Creates:
  gates_tickets   — Task 3.1

Indexes
-------
* idx_tickets_status_entry   — composite (status, entry_time)
  for "find all OPEN sessions older than 7 days" (Track 6 abandoned-ticket task).
* idx_tickets_vehicle_entry  — composite (vehicle_type, entry_time)
  for revenue aggregation by vehicle type.

Constraints (CHECK)
-------------------
* chk_ticket_vehicle_type_valid  — vehicle_type IN (MOTORCYCLE, CAR, TRUCK)
* chk_ticket_assigned_size_valid — assigned_size IN (COMPACT, REGULAR, OVERSIZED)
* chk_ticket_status_valid        — status IN (OPEN, PAID, VOIDED)
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import apps.gates.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Ticket",
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
                    "ticket_code",
                    models.CharField(
                        db_index=True,
                        default=apps.gates.models._generate_code,
                        help_text="Printed on the physical ticket stub. 12-char alphanumeric.",
                        max_length=20,
                        unique=True,
                    ),
                ),
                (
                    "vehicle_type",
                    models.CharField(
                        choices=[
                            ("MOTORCYCLE", "Motorcycle"),
                            ("CAR",        "Car"),
                            ("TRUCK",      "Truck"),
                        ],
                        db_index=True,
                        help_text="Vehicle class presented at the entry gate.",
                        max_length=15,
                    ),
                ),
                (
                    "assigned_size",
                    models.CharField(
                        choices=[
                            ("COMPACT",   "Compact"),
                            ("REGULAR",   "Regular"),
                            ("OVERSIZED", "Oversized"),
                        ],
                        db_index=True,
                        help_text=(
                            "The spot-size actually reserved by OCC "
                            "(may differ from vehicle's preferred size when overflow applies)."
                        ),
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("OPEN",   "Open"),
                            ("PAID",   "Paid"),
                            ("VOIDED", "Voided"),
                        ],
                        db_index=True,
                        default="OPEN",
                        help_text="Lifecycle state of the parking session.",
                        max_length=10,
                    ),
                ),
                (
                    "entry_time",
                    models.DateTimeField(
                        auto_now_add=True,
                        db_index=True,
                        help_text="UTC timestamp when the vehicle entered.",
                    ),
                ),
                (
                    "exit_time",
                    models.DateTimeField(
                        blank=True,
                        help_text="UTC timestamp when the vehicle exited and payment was confirmed.",
                        null=True,
                    ),
                ),
                (
                    "issued_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Attendant / service account that created this ticket.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="issued_tickets",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "gates_tickets",
                "ordering": ["-entry_time"],
            },
        ),

        # ── Composite indexes ────────────────────────────────────
        migrations.AddIndex(
            model_name="Ticket",
            index=models.Index(
                fields=["status", "entry_time"],
                name="idx_tickets_status_entry",
            ),
        ),
        migrations.AddIndex(
            model_name="Ticket",
            index=models.Index(
                fields=["vehicle_type", "entry_time"],
                name="idx_tickets_vehicle_entry",
            ),
        ),

        # ── DB-level enum guards (CheckConstraints) ──────────────
        migrations.AddConstraint(
            model_name="Ticket",
            constraint=models.CheckConstraint(
                check=models.Q(
                    vehicle_type__in=["MOTORCYCLE", "CAR", "TRUCK"]
                ),
                name="chk_ticket_vehicle_type_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="Ticket",
            constraint=models.CheckConstraint(
                check=models.Q(
                    assigned_size__in=["COMPACT", "REGULAR", "OVERSIZED"]
                ),
                name="chk_ticket_assigned_size_valid",
            ),
        ),
        migrations.AddConstraint(
            model_name="Ticket",
            constraint=models.CheckConstraint(
                check=models.Q(status__in=["OPEN", "PAID", "VOIDED"]),
                name="chk_ticket_status_valid",
            ),
        ),
    ]
