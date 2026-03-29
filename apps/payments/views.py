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
from apps.inventory.models import LotOccupancy
from apps.payments.models import PricingRule, Payment
from apps.accounts.permissions import IsAdminRole
from apps.payments.serializers import (
    TicketScanSerializer, 
    PaymentCreateSerializer,
    PricingRuleReadSerializer,
    PricingRuleUpdateSerializer
)


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

        # Calculate duration
        now = timezone.now()
        duration = now - ticket.entry_time
        duration_hours = math.ceil(duration.total_seconds() / 3600.0)
        if duration_hours < 1:
            duration_hours = 1

        # Look up PricingRule
        rule = PricingRule.objects.filter(
            vehicle_type=ticket.vehicle_type,
            spot_size=ticket.assigned_size,
            is_active=True,
        ).first()

        if not rule:
            return Response(
                {"error": "No active pricing rule found for this vehicle and spot size."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Calculate fee — max_daily_rate scales per calendar day
        num_days = max(1, math.ceil(duration.total_seconds() / 86400.0))
        calculated_fee = Decimal(duration_hours) * rule.hourly_rate
        daily_cap = rule.max_daily_rate * num_days
        final_fee = min(calculated_fee, daily_cap)

        return Response({
            "ticket_id": ticket.id,
            "ticket_code": ticket.ticket_code,
            "vehicle_type": ticket.vehicle_type,
            "assigned_size": ticket.assigned_size,
            "entry_time": ticket.entry_time,
            "duration_hours": duration_hours,
            "duration_days": num_days,
            "hourly_rate": rule.hourly_rate,
            "max_daily_rate": rule.max_daily_rate,
            "amount_owed": final_fee
        }, status=status.HTTP_200_OK)


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

        if not ticket.is_open:
            return Response(
                {"error": "Ticket is not OPEN and cannot be paid again."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Re-calculate the owed amount to prevent underpayment
        now = timezone.now()
        duration = now - ticket.entry_time
        duration_hours = max(1, math.ceil(duration.total_seconds() / 3600.0))

        rule = PricingRule.objects.filter(
            vehicle_type=ticket.vehicle_type,
            spot_size=ticket.assigned_size,
            is_active=True,
        ).first()

        if rule:
            num_days = max(1, math.ceil(duration.total_seconds() / 86400.0))
            calculated_fee = Decimal(duration_hours) * rule.hourly_rate
            daily_cap = rule.max_daily_rate * num_days
            amount_owed = min(calculated_fee, daily_cap)

            if amount_paid < amount_owed:
                return Response(
                    {
                        "error": "Insufficient payment.",
                        "amount_paid": str(amount_paid),
                        "amount_owed": str(amount_owed),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Create payment record
        payment = Payment.objects.create(
            ticket=ticket,
            processed_by=request.user,
            amount=amount_paid,
            payment_method=method,
        )

        # Update Ticket
        ticket.status = TicketStatus.PAID
        ticket.exit_time = timezone.now()
        ticket.save(update_fields=["status", "exit_time"])

        # Release the spot in LotOccupancy with OCC retry loop
        released = False
        for attempt in range(MAX_RELEASE_RETRIES):
            released = LotOccupancy.attempt_release(ticket.assigned_size)
            if released:
                break
            time.sleep(0.05)  # Brief backoff before retry

        if not released:
            logger.warning(
                "OCC release failed after %d retries for ticket %s (spot_size=%s). "
                "Occupancy counter may be stale.",
                MAX_RELEASE_RETRIES, ticket.ticket_code, ticket.assigned_size,
            )

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
    GET /api/v1/pricing-rules/{id}
    PUT/PATCH /api/v1/pricing-rules/{id}
    Allows admins to update pricing rates dynamically.
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
            .order_by("-date")
        )

        return Response(report)

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
        if date_filter:
            qs = qs.filter(entry_time__date=date_filter)

        report = (
            qs.annotate(hour=ExtractHour("entry_time"))
            .values("hour")
            .annotate(entry_count=Count("id"))
            .order_by("hour")
        )

        return Response([{"hour": item["hour"], "entry_count": item["entry_count"]} for item in report])
