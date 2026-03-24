import math
from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.gates.models import Ticket, TicketStatus
from apps.inventory.models import LotOccupancy
from apps.payments.models import PricingRule, Payment
from apps.payments.serializers import TicketScanSerializer, PaymentCreateSerializer


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

        # Calculate fee
        calculated_fee = Decimal(duration_hours) * rule.hourly_rate
        final_fee = min(calculated_fee, rule.max_daily_rate)

        return Response({
            "ticket_id": ticket.id,
            "ticket_code": ticket.ticket_code,
            "vehicle_type": ticket.vehicle_type,
            "assigned_size": ticket.assigned_size,
            "entry_time": ticket.entry_time,
            "duration_hours": duration_hours,
            "hourly_rate": rule.hourly_rate,
            "max_daily_rate": rule.max_daily_rate,
            "amount_owed": final_fee
        }, status=status.HTTP_200_OK)


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

        # Create payment record
        user = request.user if request.user.is_authenticated else None
        
        payment = Payment.objects.create(
            ticket=ticket,
            processed_by=user,
            amount=amount_paid,
            payment_method=method,
        )

        # Update Ticket
        ticket.status = TicketStatus.PAID
        ticket.exit_time = timezone.now()
        ticket.save(update_fields=["status", "exit_time"])

        # Release the spot in the LotOccupancy
        released = LotOccupancy.attempt_release(ticket.assigned_size)
        if not released:
            # Normally this means occupancy was already 0 or an OCC conflict. Log it.
            pass

        return Response({
            "message": "Payment successful. Exit gate opened.",
            "payment_id": payment.id,
            "amount_paid": payment.amount,
            "ticket_code": ticket.ticket_code,
            "exit_time": ticket.exit_time
        }, status=status.HTTP_201_CREATED)
