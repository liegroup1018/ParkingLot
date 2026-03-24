"""
Track 3 — Gates URL configuration

All routes registered under /api/v1/gates/ via config/urls.py.
"""
from django.urls import path

from .views import GateEntryView, GateOverrideView, TicketDetailView, TicketListView

app_name = "gates"

urlpatterns = [
    # ── Entry gate ───────────────────────────────────────────────
    path(
        "entry/",
        GateEntryView.as_view(),
        name="gate-entry",
    ),

    # ── Manual override (Admin) ──────────────────────────────────
    path(
        "<str:gate_id>/override/",
        GateOverrideView.as_view(),
        name="gate-override",
    ),

    # ── Ticket lookup ────────────────────────────────────────────
    path(
        "tickets/",
        TicketListView.as_view(),
        name="ticket-list",
    ),
    path(
        "tickets/<str:ticket_code>/",
        TicketDetailView.as_view(),
        name="ticket-detail",
    ),
]
