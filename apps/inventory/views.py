"""
Track 2 — Inventory Views (Task 2.3)

Admin-only CRUD for ParkingSpots + bulk-seed endpoint.
Read-only occupancy / summary endpoints (any authenticated user).

URL layout (wired in urls.py):
  GET    /api/v1/spots/                   — list all spots (paginated)
  POST   /api/v1/spots/                   — create a single spot
  GET    /api/v1/spots/<id>/              — retrieve one spot
  PATCH  /api/v1/spots/<id>/             — update status (Admin)
  DELETE /api/v1/spots/<id>/             — delete spot (Admin)
  POST   /api/v1/spots/seed/             — bulk seed (Admin)
  GET    /api/v1/spots/summary/           — counts by size/status (any auth)
  GET    /api/v1/spots/occupancy/         — OCC table snapshot (any auth)
"""
import logging

from django.db.models import Count, Q
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminRole

from .models import LotOccupancy, ParkingSpot, SpotSizeType, SpotStatus
from .serializers import (
    BulkSpotSeedSerializer,
    LotOccupancySerializer,
    ParkingSpotCreateSerializer,
    ParkingSpotReadSerializer,
    ParkingSpotUpdateSerializer,
    SpotSummarySerializer,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────
# Task 2.3 — CRUD for ParkingSpot
# ──────────────────────────────────────────────────────────────────

class ParkingSpotListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/spots/ — list spots (filterable by ?size_type= and ?status=)
    POST /api/v1/spots/ — create one spot (Admin only)
    """
    queryset = ParkingSpot.objects.all()

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ParkingSpotCreateSerializer
        return ParkingSpotReadSerializer

    def get_queryset(self):
        qs = ParkingSpot.objects.all()
        size = self.request.query_params.get("size_type")
        stat = self.request.query_params.get("status")
        if size:
            qs = qs.filter(size_type=size.upper())
        if stat:
            qs = qs.filter(status=stat.upper())
        return qs

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        spot = serializer.save()
        read_serializer = ParkingSpotReadSerializer(spot)
        logger.info(
            "Admin %s created spot %s (%s)",
            request.user.username,
            spot.spot_number,
            spot.size_type,
        )
        return Response(
            {"success": True, "data": read_serializer.data},
            status=status.HTTP_201_CREATED,
        )

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        page = self.paginate_queryset(qs)
        if page is not None:
            serializer = ParkingSpotReadSerializer(page, many=True)
            paginated = self.get_paginated_response(serializer.data)
            return Response({"success": True, "data": paginated.data})
        serializer = ParkingSpotReadSerializer(qs, many=True)
        return Response({"success": True, "data": serializer.data})


class ParkingSpotDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/v1/spots/<id>/ — retrieve spot detail (any auth)
    PATCH  /api/v1/spots/<id>/ — update status (Admin only)
    DELETE /api/v1/spots/<id>/ — delete spot (Admin only)
    """
    queryset = ParkingSpot.objects.all()

    def get_permissions(self):
        if self.request.method in ("PATCH", "DELETE"):
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return ParkingSpotUpdateSerializer
        return ParkingSpotReadSerializer

    # Disable full PUT — only partial PATCH allowed
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def update(self, request, *args, **kwargs):
        spot = self.get_object()
        serializer = ParkingSpotUpdateSerializer(
            spot, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        read_serializer = ParkingSpotReadSerializer(spot)
        logger.info(
            "Admin %s updated spot %s → status=%s",
            request.user.username,
            spot.spot_number,
            spot.status,
        )
        return Response({"success": True, "data": read_serializer.data})

    def destroy(self, request, *args, **kwargs):
        spot = self.get_object()
        spot_number = spot.spot_number
        spot.delete()
        logger.info(
            "Admin %s deleted spot %s",
            request.user.username,
            spot_number,
        )
        return Response(
            {"success": True, "message": f"Spot {spot_number} deleted."},
            status=status.HTTP_200_OK,
        )


# ──────────────────────────────────────────────────────────────────
# Task 2.3 — Bulk-seed endpoint
# ──────────────────────────────────────────────────────────────────

class BulkSpotSeedView(APIView):
    """
    POST /api/v1/spots/seed/

    Idempotent bulk creation of parking spots.
    Auto-generates spot_numbers in the format SIZE-NNNN.
    Only Admins may call this.

    Body example::

        {
            "compact_count":   3000,
            "regular_count":   5000,
            "oversized_count": 2000
        }
    """
    permission_classes = [IsAdminRole]

    def post(self, request, *args, **kwargs):
        serializer = BulkSpotSeedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        summary = serializer.create_spots()
        total_created = sum(summary.values())
        logger.info(
            "Admin %s bulk-seeded %d spots: %s",
            request.user.username,
            total_created,
            summary,
        )
        return Response(
            {
                "success": True,
                "message": f"{total_created} spots created.",
                "data": summary,
            },
            status=status.HTTP_201_CREATED,
        )


# ──────────────────────────────────────────────────────────────────
# Summary view — read-only, any authenticated user
# ──────────────────────────────────────────────────────────────────

class SpotSummaryView(APIView):
    """
    GET /api/v1/spots/summary/

    Returns aggregated counts per size type, split by status.
    Uses a single annotated queryset — no N+1.

    Example response::

        {
            "success": true,
            "data": [
                {
                    "size_type": "COMPACT",
                    "total": 3000,
                    "active": 2998,
                    "maintenance": 2
                },
                ...
            ]
        }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        rows = (
            ParkingSpot.objects
            .values("size_type")
            .annotate(
                total=Count("id"),
                active=Count(
                    "id",
                    filter=Q(status=SpotStatus.ACTIVE),
                ),
                maintenance=Count(
                    "id",
                    filter=Q(status=SpotStatus.MAINTENANCE),
                ),
            )
            .order_by("size_type")
        )
        serializer = SpotSummarySerializer(rows, many=True)
        return Response({"success": True, "data": serializer.data})


# ──────────────────────────────────────────────────────────────────
# OCC occupancy snapshot — read-only, any authenticated user
# ──────────────────────────────────────────────────────────────────

class LotOccupancyView(APIView):
    """
    GET /api/v1/spots/occupancy/

    Returns the current OCC table — one object per spot size.
    Exposes ``available`` = total_capacity − current_count.
    This is the primary data source for the real-time dashboard
    (system_design §3 → ``GET /api/v1/lot/occupancy``).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        occupancy = LotOccupancy.objects.all().order_by("spot_size")
        serializer = LotOccupancySerializer(occupancy, many=True)
        return Response({"success": True, "data": serializer.data})
