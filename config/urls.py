from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from apps.inventory.views import LotOccupancyView, PublicLotOccupancyView

urlpatterns = [
    # ── Public entry points ──────────────────────────────────────────
    path("",           TemplateView.as_view(template_name="landing.html"),    name="home"),
    path("lot-status/", TemplateView.as_view(template_name="lot_status.html"), name="lot-status"),

    # ── Django admin ─────────────────────────────────────────────────
    path("admin/", admin.site.urls),

    # ── API: core modules ────────────────────────────────────────────
    path("api/v1/auth/",  include("apps.accounts.urls")),   # Track 1 — IAM
    path("api/v1/spots/", include("apps.inventory.urls")),  # Track 2 — Inventory
    path("api/v1/gates/", include("apps.gates.urls")),      # Track 3 — Entry Gates
    path("api/v1/",       include("apps.payments.urls")),   # Track 4 — Pricing Engine & Payments

    # ── API: dashboard + analytics ───────────────────────────────────
    path("api/v1/lot/occupancy/",        LotOccupancyView.as_view(),       name="lot-occupancy-dashboard"),  # Track 6 (auth)
    path("api/v1/lot/occupancy/public/", PublicLotOccupancyView.as_view(), name="lot-occupancy-public"),     # Public Lot Status

    # ── UI shells ────────────────────────────────────────────────────
    path("attendant/",       include("apps.attendant_ui.urls")),  # Track 5 — Attendant UI
    path("admin-dashboard/", include("apps.admin_ui.urls")),      # Track 6 — Admin UI
]

