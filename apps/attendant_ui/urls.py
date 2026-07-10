"""
Track 5 — Attendant UI URL configuration

All paths are prefixed with /attendant/ from the root URLconf.
"""
from django.urls import path

from .views import (
    AttendantCheckoutView,
    AttendantDashboardView,
    AttendantEntryView,
    AttendantLoginView,
    AttendantScanTicketView,
    AttendantLostTicketView,
    AttendantManualEntryView,
    AttendantTicketLookupView,
    AttendantGateOverrideView,
)

app_name = "attendant"

urlpatterns = [
    path("", AttendantEntryView.as_view(), name="entry"),
    path("login/", AttendantLoginView.as_view(), name="login"),
    path("app/dashboard/", AttendantDashboardView.as_view(), name="dashboard"),
    path("app/scan/", AttendantScanTicketView.as_view(), name="scan_ticket"),
    path("app/lost/", AttendantLostTicketView.as_view(), name="lost_ticket"),
    path("app/checkout/", AttendantCheckoutView.as_view(), name="checkout"),
    # ── Manual gate operation pages (hardware fallback) ──────────────
    path("app/entry/", AttendantManualEntryView.as_view(), name="manual_entry"),
    path("app/ticket-lookup/", AttendantTicketLookupView.as_view(), name="ticket_lookup"),
    path("app/override/", AttendantGateOverrideView.as_view(), name="gate_override"),
]
