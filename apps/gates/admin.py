"""
Track 3 — Django Admin for Gates

Ticket: list / filter / search, bulk void action.
"""
from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest

from .models import Ticket, TicketStatus


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_code",
        "vehicle_type",
        "assigned_size",
        "status",
        "issued_by",
        "entry_time",
        "exit_time",
    )
    list_filter   = ("status", "vehicle_type", "assigned_size")
    search_fields = ("ticket_code",)
    ordering      = ("-entry_time",)
    readonly_fields = (
        "ticket_code",
        "vehicle_type",
        "assigned_size",
        "issued_by",
        "entry_time",
    )

    # Admin actions
    actions = ["void_tickets"]

    @admin.action(description="Void selected tickets (ADMIN override)")
    def void_tickets(self, request: HttpRequest, queryset: QuerySet) -> None:
        updated = queryset.filter(status=TicketStatus.OPEN).update(
            status=TicketStatus.VOIDED
        )
        self.message_user(
            request,
            f"{updated} open ticket(s) voided.",
            level="WARNING",
        )
