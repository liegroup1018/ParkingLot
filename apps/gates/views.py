"""
Track 3 — Gates views

POST /api/v1/gates/entry               — Task 3.2 (Attendant or Admin)
POST /api/v1/gates/<gate_id>/override  — Task 3.3 (Admin only)
GET  /api/v1/gates/tickets/            — list tickets (any auth)
GET  /api/v1/gates/tickets/<code>/     — retrieve one ticket by code (any auth)
"""
import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrAttendant, IsAdminRole

from .models import Ticket
from .serializers import GateEntrySerializer, GateOverrideSerializer, TicketReadSerializer
from .services import EntryService, LotFullError, OCCConflictError, OverrideService

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Helper — extract client IP
# ──────────────────────────────────────────────────────────────────

def _get_ip(request) -> str | None:
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


# ──────────────────────────────────────────────────────────────────
# Task 3.2 — Entry gate endpoint
# ──────────────────────────────────────────────────────────────────

class GateEntryView(APIView):
    """
    POST /api/v1/gates/entry

    Called by the gate hardware controller (or Attendant client) when a
    vehicle arrives.  Runs the OCC reserve + ticket creation flow.

    Request body
    ------------
    {
        "vehicle_type": "CAR",
        "gate_id":      "GATE-NORTH-01",
        "plate_number": "B 1234 ZZ"   // optional
    }

    Responses
    ---------
    201  — Ticket created (includes ticket_code for printing).
    400  — Invalid request body.
    409  — Lot is full OR OCC conflict persisted after max retries
           (gate client must display "LOT FULL" or retry).
    """
    permission_classes = [IsAdminOrAttendant]

    def post(self, request, *args, **kwargs):
        serializer = GateEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        vehicle_type  = serializer.validated_data["vehicle_type"]
        gate_id       = serializer.validated_data["gate_id"]
        plate_number  = serializer.validated_data.get("plate_number", "")

        try:
            ticket = EntryService.process_entry(
                vehicle_type=vehicle_type,
                gate_id=gate_id,
                plate_number=plate_number,
                user=request.user,
            )
        except LotFullError as exc:
            return Response(
                {
                    "success": False,
                    "code":    "LOT_FULL",
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )
        except OCCConflictError as exc:
            return Response(
                {
                    "success": False,
                    "code":    "OCC_CONFLICT",
                    "message": str(exc),
                },
                status=status.HTTP_409_CONFLICT,
            )

        read_serializer = TicketReadSerializer(ticket)
        return Response(
            {"success": True, "data": read_serializer.data},
            status=status.HTTP_201_CREATED,
        )


# ──────────────────────────────────────────────────────────────────
# Task 3.3 — Manual gate override
# ──────────────────────────────────────────────────────────────────

class GateOverrideView(APIView):
    """
    POST /api/v1/gates/<gate_id>/override

    Admin-only endpoint to open a gate without issuing a Ticket.
    Every call is written to AuditLogs as MANUAL_GATE_OPEN.

    URL param
    ---------
    gate_id : str — e.g. "GATE-NORTH-01"

    Request body
    ------------
    {
        "reason":       "Emergency vehicle access",
        "direction":    "ENTRY",         // or "EXIT"
        "plate_number": "POLICE 01"      // optional
    }

    Response
    --------
    200 — Override acknowledged (gate signalled to open).
    400 — Missing/invalid reason or direction.
    403 — Non-admin caller.
    """
    permission_classes = [IsAdminRole]

    def post(self, request, gate_id: str, *args, **kwargs):
        serializer = GateOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        summary = OverrideService.process_override(
            gate_id=gate_id,
            direction=serializer.validated_data["direction"],
            reason=serializer.validated_data["reason"],
            plate_number=serializer.validated_data.get("plate_number", ""),
            ip_address=_get_ip(request),
            user=request.user,
        )

        return Response(
            {
                "success": True,
                "message": "Gate override acknowledged. Gate signal sent.",
                "data":    summary,
            },
            status=status.HTTP_200_OK,
        )


# ──────────────────────────────────────────────────────────────────
# Ticket list / detail — read-only, any authenticated user
# ──────────────────────────────────────────────────────────────────

class TicketListView(APIView):
    """
    GET /api/v1/gates/tickets/

    Query params
    ------------
    ?status=OPEN|PAID|VOIDED
    ?vehicle_type=CAR|MOTORCYCLE|TRUCK
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        qs = Ticket.objects.select_related("issued_by").all()

        status_filter   = request.query_params.get("status")
        vehicle_filter  = request.query_params.get("vehicle_type")

        if status_filter:
            qs = qs.filter(status=status_filter.upper())
        if vehicle_filter:
            qs = qs.filter(vehicle_type=vehicle_filter.upper())

        serializer = TicketReadSerializer(qs, many=True)
        return Response({"success": True, "data": serializer.data})


class TicketDetailView(APIView):
    """
    GET /api/v1/gates/tickets/<ticket_code>/

    Lookup a ticket by its human-readable code (printed on stub).
    Used by the exit gate to pull session details for pricing (Track 4).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, ticket_code: str, *args, **kwargs):
        try:
            ticket = Ticket.objects.select_related("issued_by").get(
                ticket_code=ticket_code.upper()
            )
        except Ticket.DoesNotExist:
            return Response(
                {"success": False, "message": "Ticket not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = TicketReadSerializer(ticket)
        return Response({"success": True, "data": serializer.data})
