import logging
import math
import time
from decimal import Decimal
from django.db import models
from django.utils import timezone
from typing import Tuple, Optional

from apps.gates.models import Ticket, TicketStatus
from apps.inventory.services import InventoryService
from apps.payments.models import PricingRule, Payment

logger = logging.getLogger(__name__)

MAX_RELEASE_RETRIES = 3

class PricingError(Exception):
    pass

class PaymentError(Exception):
    pass

class PricingService:
    """
    Service for calculating fees for parking tickets based on active pricing rules.
    """

    @staticmethod
    def calculate_fee(ticket: Ticket) -> dict:
        """
        Calculates the fee for a given ticket.
        Returns a dictionary containing fee details.
        Raises PricingError if no active rule is found.
        """
        now = timezone.now()
        duration = now - ticket.entry_time
        duration_hours = max(1, math.ceil(duration.total_seconds() / 3600.0))

        current_time = now.time()
        rule = PricingRule.objects.filter(
            vehicle_type=ticket.vehicle_type,
            spot_size=ticket.assigned_size,
            is_active=True,
        ).filter(
            models.Q(time_start__lte=current_time, time_end__gte=current_time)
            | models.Q(time_start__gt=models.F("time_end"), time_start__lte=current_time)
            | models.Q(time_start__gt=models.F("time_end"), time_end__gte=current_time)
        ).first()

        if not rule:
            logger.error("No active pricing rule found for vehicle_type=%s, spot_size=%s", ticket.vehicle_type, ticket.assigned_size)
            raise PricingError("No active pricing rule found for this vehicle and spot size.")

        # Calculate fee — max_daily_rate scales per calendar day
        num_days = max(1, math.ceil(duration.total_seconds() / 86400.0))
        calculated_fee = Decimal(duration_hours) * rule.hourly_rate
        daily_cap = rule.max_daily_rate * num_days
        if ticket.status == TicketStatus.LOST:
            final_fee = rule.max_daily_rate
        else:
            final_fee = min(calculated_fee, daily_cap)

        return {
            "duration_hours": duration_hours,
            "duration_days": num_days,
            "hourly_rate": rule.hourly_rate,
            "max_daily_rate": rule.max_daily_rate,
            "amount_owed": final_fee,
        }

class PaymentService:
    """
    Service for processing payments and exiting vehicles.
    """

    @staticmethod
    def process_payment(ticket: Ticket, amount_paid: Decimal, method: str, processed_by) -> Payment:
        """
        Processes a payment for a ticket, marks it as PAID, and releases the inventory spot.
        Raises PaymentError if payment is insufficient.
        """
        # Re-calculate the owed amount to prevent underpayment
        try:
            fee_details = PricingService.calculate_fee(ticket)
            amount_owed = fee_details["amount_owed"]
        except PricingError as e:
            raise PaymentError(str(e))

        if amount_paid < amount_owed:
            raise PaymentError(f"Insufficient payment. Owed: {amount_owed}, Paid: {amount_paid}")

        # Create payment record
        payment = Payment.objects.create(
            ticket=ticket,
            processed_by=processed_by,
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
            released = InventoryService.attempt_release(ticket.assigned_size)
            if released:
                break
            time.sleep(0.05)  # Brief backoff before retry

        if not released:
            logger.warning(
                "OCC release failed after %d retries for ticket %s (spot_size=%s). "
                "Occupancy counter may be stale.",
                MAX_RELEASE_RETRIES, ticket.ticket_code, ticket.assigned_size,
            )

        return payment
