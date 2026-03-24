"""
Track 3 — Gates serializers

GateEntrySerializer      — validates POST /api/v1/gates/entry request body.
TicketReadSerializer     — read-only ticket representation returned on success.
GateOverrideSerializer   — validates POST /api/v1/gates/<gate_id>/override.
"""
from rest_framework import serializers

from apps.inventory.models import VehicleType

from .models import Ticket, TicketStatus


# ──────────────────────────────────────────────────────────────────
# Entry gate — request validation
# ──────────────────────────────────────────────────────────────────

class GateEntrySerializer(serializers.Serializer):
    """
    Validate the body of POST /api/v1/gates/entry.

    Fields
    ------
    vehicle_type : str — one of MOTORCYCLE / CAR / TRUCK (required).
    gate_id      : str — physical gate identifier, logged for traceability.
    plate_number : str — optional; stored in ticket details / audit log.
    """
    vehicle_type = serializers.ChoiceField(
        choices=VehicleType.choices,
        help_text="Vehicle class presented at the entry gate.",
    )
    gate_id = serializers.CharField(
        max_length=50,
        help_text="Physical gate identifier (e.g. 'GATE-NORTH-01').",
    )
    plate_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional licence plate captured by the gate camera.",
    )


# ──────────────────────────────────────────────────────────────────
# Ticket read (response)
# ──────────────────────────────────────────────────────────────────

class TicketReadSerializer(serializers.ModelSerializer):
    """
    Full read-only view of a Ticket returned to the gate client on success.
    """
    issued_by_username = serializers.SerializerMethodField()

    class Meta:
        model  = Ticket
        fields = [
            "id",
            "ticket_code",
            "vehicle_type",
            "assigned_size",
            "status",
            "entry_time",
            "exit_time",
            "issued_by",
            "issued_by_username",
        ]
        read_only_fields = fields

    def get_issued_by_username(self, obj: Ticket) -> str | None:
        return obj.issued_by.username if obj.issued_by else None


# ──────────────────────────────────────────────────────────────────
# Gate override — request validation  (Task 3.3)
# ──────────────────────────────────────────────────────────────────

class GateOverrideSerializer(serializers.Serializer):
    """
    Validate the body of POST /api/v1/gates/<gate_id>/override.

    A manual override allows an Admin to open a gate without issuing a
    ticket (e.g. emergency vehicle, maintenance truck, VIP access).
    The request is fully audit-logged.

    Fields
    ------
    reason     : str  — mandatory free-text reason (e.g. "Emergency exit").
    direction  : str  — ENTRY or EXIT, so the audit log records which
                        direction the gate was opened.
    plate_number: str — optional, captured for the audit trail.
    """
    DIRECTION_CHOICES = [("ENTRY", "Entry"), ("EXIT", "Exit")]

    reason = serializers.CharField(
        min_length=5,
        max_length=500,
        help_text="Mandatory reason for the manual override.",
    )
    direction = serializers.ChoiceField(
        choices=DIRECTION_CHOICES,
        default="ENTRY",
        help_text="Which direction the gate is being opened.",
    )
    plate_number = serializers.CharField(
        max_length=20,
        required=False,
        allow_blank=True,
        default="",
        help_text="Optional licence plate for traceability.",
    )
