"""
Track 2 — Inventory URL configuration

All routes registered under /api/v1/spots/ via config/urls.py.
"""
from django.urls import path

from .views import (
    BulkSpotSeedView,
    LotOccupancyView,
    ParkingSpotDetailView,
    ParkingSpotListCreateView,
    SpotSummaryView,
)

app_name = "inventory"

urlpatterns = [
    # ── Spot CRUD ────────────────────────────────────────────────
    path(
        "",
        ParkingSpotListCreateView.as_view(),
        name="spot-list-create",
    ),
    path(
        "<int:pk>/",
        ParkingSpotDetailView.as_view(),
        name="spot-detail",
    ),

    # ── Admin actions ────────────────────────────────────────────
    path(
        "seed/",
        BulkSpotSeedView.as_view(),
        name="spot-bulk-seed",
    ),

    # ── Read-only analytics ──────────────────────────────────────
    path(
        "summary/",
        SpotSummaryView.as_view(),
        name="spot-summary",
    ),
    path(
        "occupancy/",
        LotOccupancyView.as_view(),
        name="lot-occupancy",
    ),
]
