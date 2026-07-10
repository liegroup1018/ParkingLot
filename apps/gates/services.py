"""
Track 3 — Gates service layer

Isolates OCC retry + ticket creation logic from the view layer so views
stay thin and this logic is independently testable.

Public surface
--------------
``EntryService.process_entry(vehicle_type, gate_id, plate_number, user)``
    → Ticket on success
    → raises LotFullError or OCCConflictError

``OverrideService.process_override(gate_id, direction, reason, plate_number, user)``
    → dict (audit summary)

OCC retry strategy
------------------
MAX_RETRIES = 3 (configurable via Django settings).

Each attempt:
  1. Call LotOccupancy.available_size_for_vehicle() — finds first size with space.
  2. Call LotOccupancy.attempt_reserve(size) — atomic CAS update.
     Returns True  → success (create ticket).
     Returns False → either the row was grabbed by a concurrent writer
                     (OCC conflict) or the size just filled up.
  3. Retry from step 1 (up to MAX_RETRIES).
  4. Still failing after MAX_RETRIES → raise OCCConflictError (→ 409 response).
"""
import logging
from typing import Optional

from django.conf import settings
from django.db import transaction

from apps.accounts.models import AuditActionType, AuditLog
from apps.inventory.services import InventoryService

from .models import Ticket, TicketStatus

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────
_MAX_RETRIES: int = getattr(settings, "GATE_OCC_MAX_RETRIES", 3)


# ── Custom exceptions ──────────────────────────────────────────────

class LotFullError(Exception):
    """Raised when no spot is available for the vehicle type."""


class OCCConflictError(Exception):
    """
    Raised when OCC reserve consistently fails after MAX_RETRIES.
    Indicates extremely high concurrent load — caller should 409.
    """


# ──────────────────────────────────────────────────────────────────
# Task 3.2 — Entry service
# ──────────────────────────────────────────────────────────────────

class TicketCreationError(Exception):
    """
    Raised when an OCC slot was reserved but the Ticket row could not be created.
    The service compensates by releasing the reserved slot before raising.
    """


class EntryService:
    """
    Orchestrates the full entry-gate flow:
      1. Determine available spot size via overflow table.
      2. CAS-reserve the OCC row (with retries).
      3. Create Ticket atomically if step 2 succeeds.
    """

    @staticmethod
    def process_entry(
        vehicle_type: str,
        gate_id: str,
        plate_number: str,
        user,  # accounts.User
    ) -> Ticket:
        """
        Execute the OCC entry flow and return the new Ticket.

        Raises
        ------
        LotFullError     — no available size for this vehicle type.
        OCCConflictError — lot effectively full under sustained concurrency.
        TicketCreationError -- fail to create a Ticket
        """
        # Quick pre-check before entering the retry loop
        initial_size = InventoryService.available_size_for_vehicle(vehicle_type)
        if initial_size is None:
            logger.info(
                "Entry denied: lot full for vehicle_type=%s gate=%s plate=%s",
                vehicle_type, gate_id, plate_number,
            )
            raise LotFullError(f"No available spot for vehicle type: {vehicle_type}")

        # OCC retry loop (Task 3.2 — retry logic)
        for attempt in range(1, _MAX_RETRIES + 1):
            size = InventoryService.available_size_for_vehicle(vehicle_type)
            if size is None:
                # Lot drained between attempts
                raise LotFullError(
                    f"No available spot for vehicle type: {vehicle_type} "
                    f"(detected after {attempt} attempt(s))"
                )

            reserved = InventoryService.attempt_reserve(size)
            if reserved:
                # OCC succeeded — create the ticket inside a transaction
                try:
                    ticket = EntryService._create_ticket(
                        vehicle_type=vehicle_type,
                        assigned_size=size,
                        issued_by=user,
                    )
                except Exception as exc:
                    released = InventoryService.attempt_release(size)
                    if released:
                        logger.exception(
                            "Ticket creation failed after OCC reserve; released "
                            "reserved slot: vehicle=%s size=%s gate=%s plate=%s",
                            vehicle_type, size, gate_id, plate_number,
                        )
                    else:
                        logger.critical(
                            "Ticket creation failed after OCC reserve and slot "
                            "release also failed: vehicle=%s size=%s gate=%s plate=%s",
                            vehicle_type, size, gate_id, plate_number,
                            exc_info=True,
                        )
                    raise TicketCreationError(
                        "Ticket could not be created after reserving a spot."
                    ) from exc
                logger.info(
                    "Ticket %s issued: vehicle=%s size=%s gate=%s plate=%s attempt=%d",
                    ticket.ticket_code, vehicle_type, size, gate_id, plate_number, attempt,
                )
                return ticket

            # OCC version conflict — log and retry
            logger.info(
                "OCC conflict on attempt %d/%d: vehicle=%s size=%s gate=%s",
                attempt, _MAX_RETRIES, vehicle_type, size, gate_id,
            )

        # All retries exhausted
        raise OCCConflictError(
            f"OCC reserve failed after {_MAX_RETRIES} attempts. "
            "Gate client should retry."
        )

    @staticmethod
    @transaction.atomic
    def _create_ticket(vehicle_type: str, assigned_size: str, issued_by) -> Ticket:
        """
        Atomic ticket creation. The caller must compensate the OCC reservation
        if this write fails.
        """
        return Ticket.objects.create(
            vehicle_type=vehicle_type,
            assigned_size=assigned_size,
            status=TicketStatus.OPEN,
            issued_by=issued_by,
        )


# ──────────────────────────────────────────────────────────────────
# Task 3.3 — Override service
# ──────────────────────────────────────────────────────────────────

class OverrideService:
    """
    Processes a manual gate override (Admin only).

    Does NOT issue a Ticket or touch LotOccupancy.
    Writes a MANUAL_GATE_OPEN AuditLog entry.
    """

    @staticmethod
    def process_override(
        gate_id: str,
        direction: str,
        reason: str,
        plate_number: str,
        ip_address: Optional[str],
        user,   # accounts.User (must be Admin — enforced by view permission)
    ) -> dict:
        """
        Record the override and return a summary dict for the API response.
        """
        details = {
            "gate_id":      gate_id,
            "direction":    direction,
            "reason":       reason,
            "plate_number": plate_number,
        }

        AuditLog.objects.log_action(
            user=user,
            action_type=AuditActionType.MANUAL_GATE_OPEN,
            details=details,
            ip_address=ip_address,
        )

        logger.warning(
            "MANUAL GATE OVERRIDE: gate=%s direction=%s user=%s plate=%s reason=%r",
            gate_id, direction, user.username, plate_number or "N/A", reason,
        )

        return {
            "gate_id":   gate_id,
            "direction": direction,
            "opened_by": user.username,
            "reason":    reason,
        }
