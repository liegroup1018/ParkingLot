"""
Track 3 — Gates Test Suite

Covers:
  - Ticket model (code generation, uniqueness, str, is_open property)
  - EntryService (happy path, lot full, OCC retry, overflow)
  - OverrideService (audit log written, details correct)
  - POST /api/v1/gates/entry API (success, 409 scenarios, 403 non-auth)
  - POST /api/v1/gates/<gate_id>/override API (success, reason validation, 403)
  - GET  /api/v1/gates/tickets/ (list + filters)
  - GET  /api/v1/gates/tickets/<code>/ (found, 404)
"""
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AuditActionType, AuditLog
from apps.inventory.models import LotOccupancy, SpotSizeType, VehicleType

from .models import Ticket, TicketStatus
from .services import EntryService, LotFullError, OCCConflictError, OverrideService

User = get_user_model()


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def make_client(user) -> APIClient:
    client = APIClient()
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    return client


def make_admin(**kw) -> User:
    defaults = dict(username="admin", password="AdminPass1!", role="ADMIN")
    defaults.update(kw)
    return User.objects.create_user(**defaults)


def make_attendant(**kw) -> User:
    defaults = dict(username="att", password="AttPass1!", role="ATTENDANT")
    defaults.update(kw)
    return User.objects.create_user(**defaults)


def seed_occupancy(size: str, total: int, current: int = 0) -> LotOccupancy:
    return LotOccupancy.objects.create(
        spot_size=size,
        total_capacity=total,
        current_count=current,
        version=0,
    )


# ──────────────────────────────────────────────────────────────────
# Ticket model tests
# ──────────────────────────────────────────────────────────────────

class TicketModelTest(TestCase):

    def test_code_auto_generated(self):
        user = make_admin()
        t = Ticket.objects.create(
            vehicle_type=VehicleType.CAR,
            assigned_size=SpotSizeType.REGULAR,
            issued_by=user,
        )
        self.assertTrue(t.ticket_code)
        self.assertEqual(len(t.ticket_code), 12)

    def test_codes_are_unique_across_tickets(self):
        codes = {
            Ticket.objects.create(
                vehicle_type=VehicleType.CAR,
                assigned_size=SpotSizeType.REGULAR,
            ).ticket_code
            for _ in range(50)
        }
        self.assertEqual(len(codes), 50)

    def test_default_status_is_open(self):
        t = Ticket.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            assigned_size=SpotSizeType.COMPACT,
        )
        self.assertEqual(t.status, TicketStatus.OPEN)
        self.assertTrue(t.is_open)

    def test_str_contains_code_and_type(self):
        t = Ticket(
            ticket_code="ABCD1234EFGH",
            vehicle_type=VehicleType.TRUCK,
            assigned_size=SpotSizeType.OVERSIZED,
            status=TicketStatus.OPEN,
        )
        self.assertIn("ABCD1234EFGH", str(t))
        self.assertIn("TRUCK", str(t))


# ──────────────────────────────────────────────────────────────────
# EntryService tests
# ──────────────────────────────────────────────────────────────────

class EntryServiceTest(TestCase):

    def setUp(self):
        self.admin = make_admin()

    def test_happy_path_creates_ticket(self):
        seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        ticket = EntryService.process_entry(
            vehicle_type=VehicleType.CAR,
            gate_id="GATE-01",
            plate_number="B 1234 XX",
            user=self.admin,
        )
        self.assertIsInstance(ticket, Ticket)
        self.assertEqual(ticket.vehicle_type, VehicleType.CAR)
        self.assertEqual(ticket.assigned_size, SpotSizeType.REGULAR)
        self.assertEqual(ticket.status, TicketStatus.OPEN)

    def test_reserves_occ_count(self):
        seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        EntryService.process_entry(VehicleType.CAR, "G1", "", self.admin)
        row = LotOccupancy.objects.get(spot_size=SpotSizeType.REGULAR)
        self.assertEqual(row.current_count, 1)
        self.assertEqual(row.version, 1)

    def test_lot_full_raises_error(self):
        seed_occupancy(SpotSizeType.REGULAR, total=2, current=2)
        with self.assertRaises(LotFullError):
            EntryService.process_entry(VehicleType.CAR, "G1", "", self.admin)

    def test_motorcycle_overflow_to_regular(self):
        seed_occupancy(SpotSizeType.COMPACT, total=1, current=1)  # full
        seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        ticket = EntryService.process_entry(VehicleType.MOTORCYCLE, "G1", "", self.admin)
        self.assertEqual(ticket.assigned_size, SpotSizeType.REGULAR)

    def test_motorcycle_overflow_to_oversized_when_regular_also_full(self):
        seed_occupancy(SpotSizeType.COMPACT,   total=1, current=1)
        seed_occupancy(SpotSizeType.REGULAR,   total=1, current=1)
        seed_occupancy(SpotSizeType.OVERSIZED, total=3, current=0)
        ticket = EntryService.process_entry(VehicleType.MOTORCYCLE, "G1", "", self.admin)
        self.assertEqual(ticket.assigned_size, SpotSizeType.OVERSIZED)

    def test_truck_rejects_non_oversized(self):
        seed_occupancy(SpotSizeType.COMPACT, total=5, current=0)
        seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        with self.assertRaises(LotFullError):
            EntryService.process_entry(VehicleType.TRUCK, "G1", "", self.admin)

    def test_occ_conflict_raises_after_max_retries(self):
        """
        Simulate attempt_reserve always returning False (OCC conflict every time)
        even though available_size_for_vehicle always returns a size.
        """
        seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        with (
            patch(
                "apps.gates.services.LotOccupancy.available_size_for_vehicle",
                return_value=SpotSizeType.REGULAR,
            ),
            patch(
                "apps.gates.services.LotOccupancy.attempt_reserve",
                return_value=False,
            ),
        ):
            with self.assertRaises(OCCConflictError):
                EntryService.process_entry(VehicleType.CAR, "G1", "", self.admin)

    def test_retry_succeeds_on_second_attempt(self):
        """
        First attempt_reserve call returns False (conflict), second returns True.
        Ticket should still be created.
        """
        seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        with (
            patch(
                "apps.gates.services.LotOccupancy.available_size_for_vehicle",
                return_value=SpotSizeType.REGULAR,
            ),
            patch(
                "apps.gates.services.LotOccupancy.attempt_reserve",
                side_effect=[False, True],
            ),
        ):
            ticket = EntryService.process_entry(VehicleType.CAR, "G1", "", self.admin)
        self.assertIsInstance(ticket, Ticket)


# ──────────────────────────────────────────────────────────────────
# OverrideService tests
# ──────────────────────────────────────────────────────────────────

class OverrideServiceTest(TestCase):

    def setUp(self):
        self.admin = make_admin()

    def test_creates_audit_log(self):
        OverrideService.process_override(
            gate_id="GATE-SOUTH-02",
            direction="ENTRY",
            reason="Emergency ambulance access",
            plate_number="AMB 001",
            ip_address="192.168.1.10",
            user=self.admin,
        )
        log = AuditLog.objects.get(action_type=AuditActionType.MANUAL_GATE_OPEN)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.details["gate_id"], "GATE-SOUTH-02")
        self.assertEqual(log.details["direction"], "ENTRY")
        self.assertEqual(log.details["reason"], "Emergency ambulance access")
        self.assertEqual(log.ip_address, "192.168.1.10")

    def test_returns_summary_dict(self):
        result = OverrideService.process_override(
            gate_id="GATE-01",
            direction="EXIT",
            reason="Tow truck removal",
            plate_number="TOW 99",
            ip_address=None,
            user=self.admin,
        )
        self.assertEqual(result["gate_id"],   "GATE-01")
        self.assertEqual(result["direction"], "EXIT")
        self.assertEqual(result["opened_by"], self.admin.username)

    def test_no_ticket_created(self):
        OverrideService.process_override(
            gate_id="G-01", direction="ENTRY",
            reason="VIP access", plate_number="",
            ip_address=None, user=self.admin,
        )
        self.assertEqual(Ticket.objects.count(), 0)


# ──────────────────────────────────────────────────────────────────
# API — POST /api/v1/gates/entry
# ──────────────────────────────────────────────────────────────────

class GateEntryAPITest(TestCase):
    URL = "/api/v1/gates/entry/"

    def setUp(self):
        self.admin    = make_admin()
        self.attendant = make_attendant()
        self.adm_client = make_client(self.admin)
        self.att_client = make_client(self.attendant)

    def _seed(self, size, total, current=0):
        return seed_occupancy(size, total, current)

    def test_attendant_can_create_ticket(self):
        self._seed(SpotSizeType.REGULAR, 5)
        res = self.att_client.post(
            self.URL,
            {"vehicle_type": "CAR", "gate_id": "GATE-01"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(res.data["success"])
        self.assertIn("ticket_code", res.data["data"])

    def test_admin_can_create_ticket(self):
        self._seed(SpotSizeType.REGULAR, 5)
        res = self.adm_client.post(
            self.URL,
            {"vehicle_type": "CAR", "gate_id": "GATE-01"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    def test_unauthenticated_returns_401(self):
        res = self.client.post(
            self.URL,
            {"vehicle_type": "CAR", "gate_id": "GATE-01"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lot_full_returns_409(self):
        self._seed(SpotSizeType.REGULAR, 2, current=2)
        res = self.att_client.post(
            self.URL,
            {"vehicle_type": "CAR", "gate_id": "GATE-01"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data["code"], "LOT_FULL")

    def test_occ_conflict_returns_409(self):
        self._seed(SpotSizeType.REGULAR, 5)
        with (
            patch(
                "apps.gates.services.LotOccupancy.available_size_for_vehicle",
                return_value=SpotSizeType.REGULAR,
            ),
            patch(
                "apps.gates.services.LotOccupancy.attempt_reserve",
                return_value=False,
            ),
        ):
            res = self.att_client.post(
                self.URL,
                {"vehicle_type": "CAR", "gate_id": "GATE-01"},
                format="json",
            )
        self.assertEqual(res.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(res.data["code"], "OCC_CONFLICT")

    def test_invalid_vehicle_type_returns_400(self):
        res = self.att_client.post(
            self.URL,
            {"vehicle_type": "BICYCLE", "gate_id": "GATE-01"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_gate_id_returns_400(self):
        res = self.att_client.post(
            self.URL,
            {"vehicle_type": "CAR"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_occ_count_incremented_on_success(self):
        self._seed(SpotSizeType.REGULAR, 5)
        self.att_client.post(
            self.URL,
            {"vehicle_type": "CAR", "gate_id": "G1"},
            format="json",
        )
        row = LotOccupancy.objects.get(spot_size=SpotSizeType.REGULAR)
        self.assertEqual(row.current_count, 1)


# ──────────────────────────────────────────────────────────────────
# API — POST /api/v1/gates/<gate_id>/override
# ──────────────────────────────────────────────────────────────────

class GateOverrideAPITest(TestCase):
    def _url(self, gate_id="GATE-NORTH-01"):
        return f"/api/v1/gates/{gate_id}/override/"

    def setUp(self):
        self.admin    = make_admin()
        self.attendant = make_attendant()
        self.adm_client = make_client(self.admin)
        self.att_client = make_client(self.attendant)

    def test_admin_override_returns_200(self):
        res = self.adm_client.post(
            self._url(),
            {"reason": "Emergency access", "direction": "ENTRY"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertEqual(res.data["data"]["gate_id"], "GATE-NORTH-01")

    def test_attendant_cannot_override(self):
        res = self.att_client.post(
            self._url(),
            {"reason": "Emergency", "direction": "ENTRY"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_audit_log_created(self):
        self.adm_client.post(
            self._url("GATE-SOUTH-02"),
            {"reason": "VIP vehicle access", "direction": "EXIT"},
            format="json",
        )
        log = AuditLog.objects.get(action_type=AuditActionType.MANUAL_GATE_OPEN)
        self.assertEqual(log.details["gate_id"], "GATE-SOUTH-02")
        self.assertEqual(log.details["direction"], "EXIT")

    def test_short_reason_returns_400(self):
        res = self.adm_client.post(
            self._url(),
            {"reason": "Hi", "direction": "ENTRY"},  # < 5 chars
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_direction_returns_400(self):
        res = self.adm_client.post(
            self._url(),
            {"reason": "Emergency access", "direction": "SIDEWAYS"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_ticket_created_on_override(self):
        self.adm_client.post(
            self._url(),
            {"reason": "Emergency access", "direction": "ENTRY"},
            format="json",
        )
        self.assertEqual(Ticket.objects.count(), 0)


# ──────────────────────────────────────────────────────────────────
# API — GET /api/v1/gates/tickets/
# ──────────────────────────────────────────────────────────────────

class TicketListAPITest(TestCase):
    URL = "/api/v1/gates/tickets/"

    def setUp(self):
        self.admin  = make_admin()
        self.client_auth = make_client(self.admin)
        Ticket.objects.create(
            vehicle_type=VehicleType.CAR,
            assigned_size=SpotSizeType.REGULAR,
        )
        Ticket.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            assigned_size=SpotSizeType.COMPACT,
            status=TicketStatus.PAID,
        )

    def test_list_all_tickets(self):
        res = self.client_auth.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["data"]), 2)

    def test_filter_by_status(self):
        res = self.client_auth.get(f"{self.URL}?status=OPEN")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data["data"]), 1)
        self.assertEqual(res.data["data"][0]["status"], "OPEN")

    def test_filter_by_vehicle_type(self):
        res = self.client_auth.get(f"{self.URL}?vehicle_type=MOTORCYCLE")
        self.assertEqual(len(res.data["data"]), 1)
        self.assertEqual(res.data["data"][0]["vehicle_type"], "MOTORCYCLE")

    def test_unauthenticated_returns_401(self):
        res = self.client.get(self.URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ──────────────────────────────────────────────────────────────────
# API — GET /api/v1/gates/tickets/<code>/
# ──────────────────────────────────────────────────────────────────

class TicketDetailAPITest(TestCase):

    def setUp(self):
        self.admin = make_admin()
        self.client_auth = make_client(self.admin)
        self.ticket = Ticket.objects.create(
            vehicle_type=VehicleType.CAR,
            assigned_size=SpotSizeType.REGULAR,
        )

    def test_retrieve_by_code(self):
        res = self.client_auth.get(
            f"/api/v1/gates/tickets/{self.ticket.ticket_code}/"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["data"]["ticket_code"], self.ticket.ticket_code)

    def test_not_found_returns_404(self):
        res = self.client_auth.get("/api/v1/gates/tickets/DOESNOTEXIST00/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
