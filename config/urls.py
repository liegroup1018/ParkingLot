"""URL configuration for the Parking Lot Management System."""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/",  include("apps.accounts.urls")),   # Track 1 — IAM
    path("api/v1/spots/", include("apps.inventory.urls")),  # Track 2 — Inventory
    path("api/v1/gates/", include("apps.gates.urls")),      # Track 3 — Entry Gates
    path("api/v1/",       include("apps.payments.urls")),   # Track 4 — Pricing Engine & Payments
]
