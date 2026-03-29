"""
Track 5 — Attendant UI URL configuration

All paths are prefixed with /attendant/ from the root URLconf.
"""
from django.urls import path

from .views import (
    AttendantCheckoutView,
    AttendantDashboardView,
    AttendantLoginView,
    AttendantScanTicketView,
)

app_name = "attendant"

urlpatterns = [
    path("login/",    AttendantLoginView.as_view(),       name="login"),
    path("",          AttendantDashboardView.as_view(),    name="dashboard"),
    path("scan/",     AttendantScanTicketView.as_view(),   name="scan_ticket"),
    path("checkout/", AttendantCheckoutView.as_view(),     name="checkout"),
]
