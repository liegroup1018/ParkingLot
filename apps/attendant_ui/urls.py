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
)

app_name = "attendant"

urlpatterns = [
    path("", AttendantEntryView.as_view(), name="entry"),
    path("login/", AttendantLoginView.as_view(), name="login"),
    path("app/dashboard/", AttendantDashboardView.as_view(), name="dashboard"),
    path("app/scan/", AttendantScanTicketView.as_view(), name="scan_ticket"),
    path("app/lost/", AttendantLostTicketView.as_view(), name="lost_ticket"),
    path("app/checkout/", AttendantCheckoutView.as_view(), name="checkout"),
]
