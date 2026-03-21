"""
Track 2 — Inventory Test Suite

Covers:
  - ParkingSpot model (field validation, constraints)
  - LotOccupancy OCC helpers (reserve, release, overflow detection)
  - Admin CRUD API (list, create, update, delete)
  - Bulk seed API (idempotency, cap enforcement)
  - Summary / occupancy read endpoints
  - init_lot_occupancy management command
"""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import LotOccupancy, ParkingSpot, SpotSizeType, SpotStatus, VehicleType

User = get_user_model()


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def make_client(user) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def make_admin(**kwargs) -> User:
    defaults = dict(username="admin", password="AdminPass1!", role="ADMIN")
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


def make_attendant(**kwargs) -> User:
    defaults = dict(username="att", password="AttPass1!", role="ATTENDANT")
    defaults.update(kwargs)
    return User.objects.create_user(**defaults)


# ──────────────────────────────────────────────────────────────────
# Model tests
# ──────────────────────────────────────────────────────────────────

class ParkingSpotModelTest(TestCase):
    def test_create_spot_defaults_active(self):
        spot = ParkingSpot.objects.create(
            spot_number="A-001",
            size_type=SpotSizeType.COMPACT,
        )
        self.assertEqual(spot.status, SpotStatus.ACTIVE)

    def test_spot_number_is_unique(self):
        ParkingSpot.objects.create(
            spot_number="A-001",
            size_type=SpotSizeType.COMPACT,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            ParkingSpot.objects.create(
                spot_number="A-001",
                size_type=SpotSizeType.REGULAR,
            )

    def test_str_representation(self):
        spot = ParkingSpot(
            spot_number="B-002",
            size_type=SpotSizeType.REGULAR,
            status=SpotStatus.MAINTENANCE,
        )
        self.assertIn("B-002", str(spot))
        self.assertIn("REGULAR", str(spot))


# ──────────────────────────────────────────────────────────────────
# OCC LotOccupancy tests
# ──────────────────────────────────────────────────────────────────

class LotOccupancyOCCTest(TestCase):

    def setUp(self):
        LotOccupancy.objects.create(
            spot_size=SpotSizeType.COMPACT,
            total_capacity=2,
            current_count=0,
            version=0,
        )
        LotOccupancy.objects.create(
            spot_size=SpotSizeType.REGULAR,
            total_capacity=3,
            current_count=3,   # FULL
            version=10,
        )

    # ── Reserve ──────────────────────────────────────────────────

    def test_reserve_success(self):
        result = LotOccupancy.attempt_reserve(SpotSizeType.COMPACT)
        self.assertTrue(result)
        row = LotOccupancy.objects.get(spot_size=SpotSizeType.COMPACT)
        self.assertEqual(row.current_count, 1)
        self.assertEqual(row.version, 1)

    def test_reserve_fails_when_full(self):
        result = LotOccupancy.attempt_reserve(SpotSizeType.REGULAR)
        self.assertFalse(result)

    def test_reserve_increments_version(self):
        LotOccupancy.attempt_reserve(SpotSizeType.COMPACT)
        LotOccupancy.attempt_reserve(SpotSizeType.COMPACT)
        row = LotOccupancy.objects.get(spot_size=SpotSizeType.COMPACT)
        # capacity=2, both succeed
        self.assertEqual(row.current_count, 2)
        self.assertEqual(row.version, 2)

    def test_reserve_third_attempt_fails(self):
        LotOccupancy.attempt_reserve(SpotSizeType.COMPACT)
        LotOccupancy.attempt_reserve(SpotSizeType.COMPACT)
        result = LotOccupancy.attempt_reserve(SpotSizeType.COMPACT)
        self.assertFalse(result)

    def test_reserve_nonexistent_size_returns_false(self):
        result = LotOccupancy.attempt_reserve("NONEXISTENT")
        self.assertFalse(result)

    # ── Release ──────────────────────────────────────────────────

    def test_release_success(self):
        # First reserve one
        LotOccupancy.attempt_reserve(SpotSizeType.COMPACT)
        result = LotOccupancy.attempt_release(SpotSizeType.COMPACT)
        self.assertTrue(result)
        row = LotOccupancy.objects.get(spot_size=SpotSizeType.COMPACT)
        self.assertEqual(row.current_count, 0)

    def test_release_at_zero_returns_false(self):
        result = LotOccupancy.attempt_release(SpotSizeType.COMPACT)
        self.assertFalse(result)

    # ── Overflow detection ────────────────────────────────────────

    def test_available_size_motorcycle_prefers_compact(self):
        size = LotOccupancy.available_size_for_vehicle(VehicleType.MOTORCYCLE)
        self.assertEqual(size, SpotSizeType.COMPACT)

    def test_available_size_car_skips_compact(self):
        # No OVERSIZED row → car should return None (REGULAR is full)
        size = LotOccupancy.available_size_for_vehicle(VehicleType.CAR)
        self.assertIsNone(size)

    def test_available_size_falls_back_on_full_compact(self):
        # Fill COMPACT, MOTORCYCLE should fall back to... REGULAR
        # But REGULAR is also full → returns None
        LotOccupancy.objects.filter(
            spot_size=SpotSizeType.COMPACT
        ).update(current_count=2)
        size = LotOccupancy.available_size_for_vehicle(VehicleType.MOTORCYCLE)
        self.assertIsNone(size)

    def test_available_size_oversized_fallback(self):
        LotOccupancy.objects.create(
            spot_size=SpotSizeType.OVERSIZED,
            total_capacity=5,
            current_count=0,
        )
        # COMPACT full, REGULAR full, OVERSIZED available → motorcycle gets OVERSIZED
        LotOccupancy.objects.filter(
            spot_size=SpotSizeType.COMPACT
        ).update(current_count=2)
        size = LotOccupancy.available_size_for_vehicle(VehicleType.MOTORCYCLE)
        self.assertEqual(size, SpotSizeType.OVERSIZED)

    def test_truck_only_accepts_oversized(self):
        size = LotOccupancy.available_size_for_vehicle(VehicleType.TRUCK)
        self.assertIsNone(size)  # No OVERSIZED row in setUp


# ──────────────────────────────────────────────────────────────────
# API — single spot CRUD
# ──────────────────────────────────────────────────────────────────

class SpotCRUDAPITest(TestCase):

    def setUp(self):
        self.admin    = make_admin()
        self.attendant = make_attendant()
        self.adm_client = make_client(self.admin)
        self.att_client = make_client(self.attendant)
        self.base_url = "/api/v1/spots/"

    def test_admin_can_create_spot(self):
        res = self.adm_client.post(
            self.base_url,
            {"spot_number": "Z-001", "size_type": "COMPACT"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["data"]["status"], SpotStatus.ACTIVE)

    def test_attendant_cannot_create_spot(self):
        res = self.att_client.post(
            self.base_url,
            {"spot_number": "Z-002", "size_type": "COMPACT"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_create(self):
        res = self.client.post(
            self.base_url,
            {"spot_number": "Z-003", "size_type": "COMPACT"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_spots(self):
        ParkingSpot.objects.create(spot_number="A-001", size_type=SpotSizeType.REGULAR)
        res = self.att_client.get(self.base_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])

    def test_filter_by_size_type(self):
        ParkingSpot.objects.create(spot_number="A-001", size_type=SpotSizeType.COMPACT)
        ParkingSpot.objects.create(spot_number="B-001", size_type=SpotSizeType.REGULAR)
        res = self.att_client.get(f"{self.base_url}?size_type=COMPACT")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_admin_can_update_spot_status(self):
        spot = ParkingSpot.objects.create(
            spot_number="A-001", size_type=SpotSizeType.COMPACT
        )
        res = self.adm_client.patch(
            f"{self.base_url}{spot.pk}/",
            {"status": "MAINTENANCE"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        spot.refresh_from_db()
        self.assertEqual(spot.status, SpotStatus.MAINTENANCE)

    def test_attendant_cannot_update_spot(self):
        spot = ParkingSpot.objects.create(
            spot_number="A-001", size_type=SpotSizeType.COMPACT
        )
        res = self.att_client.patch(
            f"{self.base_url}{spot.pk}/",
            {"status": "MAINTENANCE"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_delete_spot(self):
        spot = ParkingSpot.objects.create(
            spot_number="A-001", size_type=SpotSizeType.COMPACT
        )
        res = self.adm_client.delete(f"{self.base_url}{spot.pk}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(ParkingSpot.objects.filter(pk=spot.pk).exists())

    def test_duplicate_spot_number_returns_400(self):
        ParkingSpot.objects.create(spot_number="DUP-001", size_type=SpotSizeType.COMPACT)
        res = self.adm_client.post(
            self.base_url,
            {"spot_number": "DUP-001", "size_type": "REGULAR"},
            format="json",
        )
        self.assertIn(res.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT])


# ──────────────────────────────────────────────────────────────────
# API — bulk seed
# ──────────────────────────────────────────────────────────────────

class BulkSeedAPITest(TestCase):

    def setUp(self):
        self.admin = make_admin()
        self.adm_client = make_client(self.admin)
        self.seed_url = "/api/v1/spots/seed/"

    def test_bulk_seed_creates_spots(self):
        res = self.adm_client.post(
            self.seed_url,
            {"compact_count": 5, "regular_count": 3, "oversized_count": 2},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ParkingSpot.objects.count(), 10)

    def test_bulk_seed_is_idempotent(self):
        self.adm_client.post(
            self.seed_url,
            {"compact_count": 5},
            format="json",
        )
        # Second call appends (doesn't duplicate)
        self.adm_client.post(
            self.seed_url,
            {"compact_count": 5},
            format="json",
        )
        # Should have 10 unique spots, not 5 with conflicts
        self.assertEqual(ParkingSpot.objects.count(), 10)

    def test_bulk_seed_zero_all_returns_400(self):
        res = self.adm_client.post(
            self.seed_url,
            {"compact_count": 0, "regular_count": 0, "oversized_count": 0},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attendant_cannot_seed(self):
        attendant = make_attendant(username="att2")
        att_client = make_client(attendant)
        res = att_client.post(
            self.seed_url,
            {"compact_count": 5},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)


# ──────────────────────────────────────────────────────────────────
# API — summary and occupancy endpoints
# ──────────────────────────────────────────────────────────────────

class SummaryAndOccupancyAPITest(TestCase):

    def setUp(self):
        self.admin = make_admin()
        self.client_auth = make_client(self.admin)
        ParkingSpot.objects.create(
            spot_number="C-001", size_type=SpotSizeType.COMPACT
        )
        ParkingSpot.objects.create(
            spot_number="C-002",
            size_type=SpotSizeType.COMPACT,
            status=SpotStatus.MAINTENANCE,
        )
        LotOccupancy.objects.create(
            spot_size=SpotSizeType.COMPACT,
            total_capacity=10,
            current_count=3,
        )

    def test_summary_endpoint(self):
        res = self.client_auth.get("/api/v1/spots/summary/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        row = next(
            (r for r in res.data["data"] if r["size_type"] == "COMPACT"),
            None,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["total"], 2)
        self.assertEqual(row["active"], 1)
        self.assertEqual(row["maintenance"], 1)

    def test_occupancy_endpoint(self):
        res = self.client_auth.get("/api/v1/spots/occupancy/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        row = res.data["data"][0]
        self.assertEqual(row["spot_size"], SpotSizeType.COMPACT)
        self.assertEqual(row["available"], 7)   # 10 - 3

    def test_unauthenticated_cannot_see_occupancy(self):
        res = self.client.get("/api/v1/spots/occupancy/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ──────────────────────────────────────────────────────────────────
# Management command
# ──────────────────────────────────────────────────────────────────

class InitLotOccupancyCommandTest(TestCase):

    def test_creates_rows_from_spots(self):
        ParkingSpot.objects.create(
            spot_number="COMPACT-0001", size_type=SpotSizeType.COMPACT
        )
        ParkingSpot.objects.create(
            spot_number="COMPACT-0002", size_type=SpotSizeType.COMPACT
        )
        ParkingSpot.objects.create(
            spot_number="REGULAR-0001", size_type=SpotSizeType.REGULAR
        )
        out = StringIO()
        call_command("init_lot_occupancy", stdout=out)

        compact = LotOccupancy.objects.get(spot_size=SpotSizeType.COMPACT)
        regular = LotOccupancy.objects.get(spot_size=SpotSizeType.REGULAR)
        self.assertEqual(compact.total_capacity, 2)
        self.assertEqual(regular.total_capacity, 1)

    def test_resets_counts_by_default(self):
        LotOccupancy.objects.create(
            spot_size=SpotSizeType.COMPACT,
            total_capacity=10,
            current_count=5,
            version=5,
        )
        ParkingSpot.objects.create(
            spot_number="COMPACT-0001", size_type=SpotSizeType.COMPACT
        )
        out = StringIO()
        call_command("init_lot_occupancy", stdout=out)

        row = LotOccupancy.objects.get(spot_size=SpotSizeType.COMPACT)
        self.assertEqual(row.current_count, 0)
        self.assertEqual(row.version, 0)

    def test_keep_counts_flag_preserves_current_count_and_version(self):
        LotOccupancy.objects.create(
            spot_size=SpotSizeType.COMPACT,
            total_capacity=10,
            current_count=4,
            version=4,
        )
        ParkingSpot.objects.create(
            spot_number="COMPACT-0001", size_type=SpotSizeType.COMPACT
        )
        out = StringIO()
        call_command("init_lot_occupancy", "--keep-counts", stdout=out)

        row = LotOccupancy.objects.get(spot_size=SpotSizeType.COMPACT)
        # total_capacity updated to 1 (only 1 ACTIVE spot now)
        self.assertEqual(row.total_capacity, 1)
        # current_count and version untouched
        self.assertEqual(row.current_count, 4)
        self.assertEqual(row.version, 4)

    def test_excludes_maintenance_spots_from_capacity(self):
        ParkingSpot.objects.create(
            spot_number="COMPACT-0001", size_type=SpotSizeType.COMPACT
        )
        ParkingSpot.objects.create(
            spot_number="COMPACT-0002",
            size_type=SpotSizeType.COMPACT,
            status=SpotStatus.MAINTENANCE,
        )
        out = StringIO()
        call_command("init_lot_occupancy", stdout=out)

        row = LotOccupancy.objects.get(spot_size=SpotSizeType.COMPACT)
        self.assertEqual(row.total_capacity, 1)  # Only ACTIVE spot counted
