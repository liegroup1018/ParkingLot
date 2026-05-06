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
