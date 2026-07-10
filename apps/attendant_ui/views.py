"""
Track 5 — Attendant UI Views

Serves server-rendered Django templates for the Attendant Dashboard.
Authentication is handled client-side via JWT tokens stored in
localStorage; these views simply render the templates.

URL layout (wired via config/urls.py → /attendant/):
  GET  /attendant/              → dashboard
  GET  /attendant/scan/         → scan ticket page
  GET  /attendant/checkout/     → payment checkout page
  GET  /attendant/login/        → login page
  GET  /attendant/app/entry/         → manual gate entry (hardware fallback)
  GET  /attendant/app/ticket-lookup/ → ticket lookup by code
  GET  /attendant/app/override/      → admin gate override (admin only)
"""
from django.shortcuts import render
from django.views import View


class AttendantEntryView(View):
    """Render the public attendant entry point."""

    def get(self, request):
        return render(request, "attendant/login.html")


class AttendantLoginView(View):
    """Render the login page (no server-side auth required)."""

    def get(self, request):
        return render(request, "attendant/login.html")


class AttendantDashboardView(View):
    """
    Render the real-time occupancy dashboard.

    Data is fetched client-side from:
      - GET /api/v1/spots/occupancy/
      - GET /api/v1/gates/tickets/?status=OPEN
    """

    def get(self, request):
        return render(request, "attendant/dashboard.html", {
            "active_page": "dashboard",
        })


class AttendantScanTicketView(View):
    """
    Render the ticket scanning / fee calculation page.

    Client-side logic calls:
      - POST /api/v1/tickets/scan
    """

    def get(self, request):
        return render(request, "attendant/scan_ticket.html", {
            "active_page": "scan",
        })


class AttendantLostTicketView(View):
    """
    Render the lost ticket creation page.

    Client-side logic calls:
      - POST /api/v1/tickets/lost/
    """

    def get(self, request):
        return render(request, "attendant/lost_ticket.html", {
            "active_page": "scan",
        })


class AttendantCheckoutView(View):
    """
    Render the payment checkout page.

    Client-side logic calls:
      - POST /api/v1/payments
    """

    def get(self, request):
        return render(request, "attendant/checkout.html", {
            "active_page": "checkout",
        })


# ──────────────────────────────────────────────────────────────────
# Manual Gate Operation pages — hardware fallback
# ──────────────────────────────────────────────────────────────────

class AttendantManualEntryView(View):
    """
    Render the manual gate entry page.

    Used when the entry barrier hardware malfunctions. Attendant manually
    registers a vehicle arrival.

    Client-side logic calls:
      - POST /api/v1/gates/entry/
    """

    def get(self, request):
        return render(request, "attendant/manual_entry.html", {
            "active_page": "entry",
        })


class AttendantTicketLookupView(View):
    """
    Render the ticket lookup page.

    Allows any authenticated user to look up a ticket by its printed code.
    Useful for verifying a paper stub when the barcode scanner is down.

    Client-side logic calls:
      - GET /api/v1/gates/tickets/<ticket_code>/
    """

    def get(self, request):
        return render(request, "attendant/ticket_lookup.html", {
            "active_page": "lookup",
        })


class AttendantGateOverrideView(View):
    """
    Render the gate override page (admin only).

    Allows an admin to manually open any gate without issuing a ticket.
    Real authorisation is enforced by IsAdminRole on the API;
    this view merely serves the HTML shell.

    Client-side logic calls:
      - POST /api/v1/gates/<gate_id>/override/
    """

    def get(self, request):
        return render(request, "attendant/gate_override.html", {
            "active_page": "override",
        })
