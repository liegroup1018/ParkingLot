import logging
import math
from decimal import Decimal

import time

from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, ExtractHour

from django.utils import timezone
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.gates.models import Ticket, TicketStatus
from apps.inventory.models import LotOccupancy, VEHICLE_SPOT_PRIORITY
from apps.payments.models import PricingRule, Payment
from apps.accounts.permissions import IsAdminRole
from apps.accounts.models import AuditLog, AuditActionType
from apps.payments.serializers import (
    TicketScanSerializer, 
    PaymentCreateSerializer,
    PricingRuleReadSerializer,
    PricingRuleUpdateSerializer,
    LostTicketCreateSerializer
)
from apps.payments.services import PricingService, PaymentService, PricingError, PaymentError


class TicketScanView(APIView):
    """
    POST /api/v1/tickets/scan
    Scans a ticket and calculates the dynamic fee based on duration.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = TicketScanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket_code = serializer.validated_data["ticket_code"]

        try:
            ticket = Ticket.objects.get(ticket_code=ticket_code)
        except Ticket.DoesNotExist:
            return Response({"error": "Ticket not found."}, status=status.HTTP_404_NOT_FOUND)

        if not ticket.is_open:
            return Response(
                {"error": f"Ticket is not OPEN. Current status: {ticket.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            fee_details = PricingService.calculate_fee(ticket)
        except PricingError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            "ticket_id": ticket.id,
            "ticket_code": ticket.ticket_code,
            "vehicle_type": ticket.vehicle_type,
            "assigned_size": ticket.assigned_size,
            "entry_time": ticket.entry_time,
            **fee_details
        }, status=status.HTTP_200_OK)


class LostTicketCreateView(APIView):
    """
    POST /api/v1/tickets/lost/
    Generates a surrogate lost ticket and returns the max daily fee.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = LostTicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle_type = serializer.validated_data["vehicle_type"]

        # Determine the default assigned size for this vehicle type
        assigned_size = VEHICLE_SPOT_PRIORITY[vehicle_type][0]

        # Create the surrogate lost ticket
        ticket = Ticket.objects.create(
            vehicle_type=vehicle_type,
            assigned_size=assigned_size,
            status=TicketStatus.LOST,
            issued_by=request.user
        )

        # Calculate fee (PricingService defaults to max_daily_rate for LOST)
        try:
            fee_details = PricingService.calculate_fee(ticket)
        except PricingError as e:
            ticket.delete() # cleanup
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            "ticket_id": ticket.id,
            "ticket_code": ticket.ticket_code,
            "vehicle_type": ticket.vehicle_type,
            "assigned_size": ticket.assigned_size,
            "entry_time": ticket.entry_time,
            **fee_details
        }, status=status.HTTP_201_CREATED)


logger = logging.getLogger(__name__)

MAX_RELEASE_RETRIES = 3


class PaymentProcessView(APIView):
    """
    POST /api/v1/payments
    Processes payment, marks ticket as PAID, and restores spot inventory.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = PaymentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        ticket_code = data.pop("ticket_id")
        amount_paid = data.pop("amount_paid")
        method = data.pop("method")

        try:
            ticket = Ticket.objects.get(ticket_code=ticket_code)
        except Ticket.DoesNotExist:
            return Response({"error": "Ticket not found."}, status=status.HTTP_404_NOT_FOUND)

        if not ticket.is_open and ticket.status != TicketStatus.LOST:
            return Response(
                {"error": "Ticket is not OPEN and cannot be paid again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payment = PaymentService.process_payment(ticket, amount_paid, method, request.user)
        except PaymentError as e:
            error_msg = str(e)
            if "Insufficient payment" in error_msg:
                # Need to parse the error message to return exact owed and paid amounts to match the original API response structure
                try:
                    # "Insufficient payment. Owed: {amount_owed}, Paid: {amount_paid}"
                    parts = error_msg.split("Owed: ")[1].split(", Paid: ")
                    amount_owed = parts[0]
                    amount_paid_str = parts[1]
                    return Response(
                        {
                            "error": "Insufficient payment.",
                            "amount_paid": amount_paid_str,
                            "amount_owed": amount_owed,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                except Exception:
                    pass
            return Response({"error": error_msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Payment successful. Exit gate opened.",
            "payment_id": payment.id,
            "amount_paid": str(payment.amount),
            "ticket_code": ticket.ticket_code,
            "exit_time": ticket.exit_time
        }, status=status.HTTP_201_CREATED)


# ──────────────────────────────────────────────────────────────────
# Track 6: Pricing Rule Management
# ──────────────────────────────────────────────────────────────────

class PricingRuleUpdateView(generics.RetrieveUpdateAPIView):
    """
    GET /api/v1/pricing-rules/{id}/
    PUT/PATCH /api/v1/pricing-rules/{id}/
    .Allows admins to update pricing rates dynamically
    Writes to AuditLog on every successful mutation (PRD §4.2).
    """
    queryset = PricingRule.objects.all()

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return PricingRuleUpdateSerializer
        return PricingRuleReadSerializer

    def perform_update(self, serializer):
        rule = self.get_object()
        old_values = {
            "hourly_rate": str(rule.hourly_rate),
            "max_daily_rate": str(rule.max_daily_rate),
            "is_active": rule.is_active,
        }
        updated = serializer.save()
        new_values = {
            "hourly_rate": str(updated.hourly_rate),
            "max_daily_rate": str(updated.max_daily_rate),
            "is_active": updated.is_active,
        }
        # Extract client IP
        ip = self.request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        if not ip:
            ip = self.request.META.get("REMOTE_ADDR")
        AuditLog.objects.create(
            user=self.request.user,
            action_type=AuditActionType.PRICE_CHANGE,
            details={"rule_id": rule.pk, "old": old_values, "new": new_values},
            ip_address=ip,
        )
        logger.info(
            "Admin %s updated PricingRule %d: %s → %s",
            self.request.user.username, rule.pk, old_values, new_values,
        )


# ──────────────────────────────────────────────────────────────────
# Track 6: Revenue Analytics
# ──────────────────────────────────────────────────────────────────

class RevenueReportView(APIView):
    """
    GET /api/v1/reports/revenue
    Returns payments aggregated by date.
    Admin only.
    """
    permission_classes = [IsAdminRole]

    def get(self, request, *args, **kwargs):
        qs = Payment.objects.filter(status="SUCCESS")

        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        if start_date:
            qs = qs.filter(payment_time__date__gte=start_date)
        if end_date:
            qs = qs.filter(payment_time__date__lte=end_date)

        report = (
            qs.annotate(date=TruncDate("payment_time"))
            .values("date")
            .annotate(total_revenue=Sum("amount"), payment_count=Count("id"))
            .order_by("date")
        )

        # Serialize date/Decimal to JSON-safe types for frontend Chart.js
        return Response([
            {
                "date": str(row["date"]),
                "total_revenue": float(row["total_revenue"] or 0),
                "payment_count": row["payment_count"],
            }
            for row in report
        ])

class PeakHoursReportView(APIView):
    """
    GET /api/v1/reports/peak-hours
    Returns ticket entries grouped by hour of the day.
    Admin only.
    """
    permission_classes = [IsAdminRole]

    def get(self, request, *args, **kwargs):
        qs = Ticket.objects.all()
        date_filter = request.query_params.get("date")
        if not date_filter:
            # Default to today so the chart matches its "Today" label
            date_filter = timezone.now().date()
        qs = qs.filter(entry_time__date=date_filter)

        report = (
            qs.annotate(hour=ExtractHour("entry_time"))
            .values("hour")
            .annotate(entry_count=Count("id"))
            .order_by("hour")
        )

        return Response([{"hour": item["hour"], "entry_count": item["entry_count"]} for item in report])
