from django.contrib import admin
from django.urls import include, path

from apps.inventory.views import LotOccupancyView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/",  include("apps.accounts.urls")),   # Track 1 — IAM
    path("api/v1/spots/", include("apps.inventory.urls")),  # Track 2 — Inventory
    path("api/v1/gates/", include("apps.gates.urls")),      # Track 3 — Entry Gates
    path("api/v1/",       include("apps.payments.urls")),   # Track 4 — Pricing Engine & Payments
    path("api/v1/lot/occupancy/", LotOccupancyView.as_view(), name="lot-occupancy-dashboard"), # Track 6
    path("attendant/",    include("apps.attendant_ui.urls")),  # Track 5 — Attendant UI
    path("admin-dashboard/", include("apps.admin_ui.urls")),  # Track 6 — Admin UI
]
