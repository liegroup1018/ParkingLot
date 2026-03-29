import logging
from datetime import timedelta

from django.utils import timezone
from django.core.management.base import BaseCommand
from apps.gates.models import Ticket, TicketStatus

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Scans for abandoned vehicles (tickets open > 7 days)."

    def handle(self, *args, **options):
        now = timezone.now()
        threshold = now - timedelta(days=7)

        # Composite index (status, entry_time) makes this query efficient
        abandoned_tickets = Ticket.objects.filter(
            status=TicketStatus.OPEN,
            entry_time__lt=threshold
        )

        count = abandoned_tickets.count()
        if count == 0:
            self.stdout.write(self.style.SUCCESS("No abandoned tickets found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {count} abandoned ticket(s)."))
        
        for ticket in abandoned_tickets:
            msg = f"Abandoned Ticket | ID: {ticket.id} | Code: {ticket.ticket_code} | Entry: {ticket.entry_time}"
            logger.warning(msg)
            self.stdout.write(msg)

        self.stdout.write(self.style.SUCCESS(f"Successfully scanned {count} abandoned ticket(s)."))
