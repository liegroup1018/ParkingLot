"""
Track 4 & 6 — Payments Test Suite

Covers:
  - PricingService (fee calculation logic, missing rules)
  - PaymentService (processing payment, state changes, OCC release)
  - TicketScanView (API dynamic fee response)
  - PaymentProcessView (API payment completion)
  - PricingRuleUpdateView (Admin edits and audit logs)
  - Reporting Views (Revenue, Peak Hours)
"""

from decimal import Decimal
from datetime import timedelta
import datetime
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AuditLog, AuditActionType
from apps.gates.models import Ticket, TicketStatus
from apps.inventory.models import SpotSizeType, VehicleType
from apps.payments.models import Payment, PricingRule
from apps.payments.services import PaymentError, PaymentService, PricingError, PricingService

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
# Service Tests
# ──────────────────────────────────────────────────────────────────

class PricingServiceTest(TestCase):
    def setUp(self):
        PricingRule.objects.all().delete()
        self.admin = make_admin()
        self.rule = PricingRule.objects.create(
            vehicle_type=VehicleType.CAR,
            spot_size=SpotSizeType.REGULAR,
            hourly_rate=Decimal("10.00"),
            max_daily_rate=Decimal("50.00"),
            is_active=True,
            time_start=datetime.time(0, 0),
            time_end=datetime.time(23, 59),
        )
        self.ticket = Ticket.objects.create(
            vehicle_type=VehicleType.CAR,
            assigned_size=SpotSizeType.REGULAR,
            issued_by=self.admin,
        )

    def test_calculate_fee_under_daily_cap(self):
        # 2 hours 59 minutes ensures math.ceil handles millisecond elapsed time predictably
        self.ticket.entry_time = timezone.now() - timedelta(hours=2, minutes=59)
        self.ticket.save()

        fee = PricingService.calculate_fee(self.ticket)
        self.assertEqual(fee["duration_hours"], 3)
        self.assertEqual(fee["amount_owed"], Decimal("30.00"))

    def test_calculate_fee_hits_daily_cap(self):
        # 5 hours 59 minutes rounds up to 6 hours
        self.ticket.entry_time = timezone.now() - timedelta(hours=5, minutes=59)
        self.ticket.save()

        fee = PricingService.calculate_fee(self.ticket)
        self.assertEqual(fee["duration_hours"], 6)
        self.assertEqual(fee["amount_owed"], Decimal("50.00"))

    def test_calculate_fee_multi_day(self):
        # 24 hours 59 minutes rounds up to 25 hours (2 days)
        self.ticket.entry_time = timezone.now() - timedelta(hours=24, minutes=59)
        self.ticket.save()

        fee = PricingService.calculate_fee(self.ticket)
        self.assertEqual(fee["duration_hours"], 25)
        self.assertEqual(fee["duration_days"], 2)
        self.assertEqual(fee["amount_owed"], Decimal("100.00"))

    def test_missing_pricing_rule_raises_error(self):
        self.rule.is_active = False
        self.rule.save()

        with self.assertRaises(PricingError):
            PricingService.calculate_fee(self.ticket)


class PaymentServiceTest(TestCase):
    def setUp(self):
        PricingRule.objects.all().delete()
        self.attendant = make_attendant()
        PricingRule.objects.create(
            vehicle_type=VehicleType.CAR,
            spot_size=SpotSizeType.REGULAR,
            hourly_rate=Decimal("10.00"),
            max_daily_rate=Decimal("50.00"),
            is_active=True,
            time_start=datetime.time(0, 0),
            time_end=datetime.time(23, 59),
        )
        self.ticket = Ticket.objects.create(
            vehicle_type=VehicleType.CAR,
            assigned_size=SpotSizeType.REGULAR,
            issued_by=self.attendant,
        )
        # Entry 1 hour 59 mins ago -> rounds to 2 hours -> fee $20
        self.ticket.entry_time = timezone.now() - timedelta(hours=1, minutes=59)
        self.ticket.save()

    @patch("apps.payments.services.InventoryService.attempt_release")
    def test_process_payment_success(self, mock_release):
        mock_release.return_value = True

        payment = PaymentService.process_payment(
            ticket=self.ticket,
            amount_paid=Decimal("20.00"),
            method="CASH",
            processed_by=self.attendant,
        )

        self.assertEqual(payment.amount, Decimal("20.00"))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.PAID)
        self.assertIsNotNone(self.ticket.exit_time)
        mock_release.assert_called_once_with(SpotSizeType.REGULAR)

    def test_process_payment_insufficient_funds(self):
        with self.assertRaises(PaymentError) as context:
            PaymentService.process_payment(
                ticket=self.ticket,
                amount_paid=Decimal("15.00"),
                method="CASH",
                processed_by=self.attendant,
            )
        self.assertIn("Insufficient payment", str(context.exception))


# ──────────────────────────────────────────────────────────────────
# API Views Tests
# ──────────────────────────────────────────────────────────────────

class PaymentsAPITest(TestCase):
    def setUp(self):
        PricingRule.objects.all().delete()
        self.attendant = make_attendant()
        self.client = make_client(self.attendant)
        
        PricingRule.objects.create(
            vehicle_type=VehicleType.CAR,
            spot_size=SpotSizeType.REGULAR,
            hourly_rate=Decimal("10.00"),
            max_daily_rate=Decimal("50.00"),
            is_active=True,
            time_start=datetime.time(0, 0),
            time_end=datetime.time(23, 59),
        )
        
        self.ticket = Ticket.objects.create(
            vehicle_type=VehicleType.CAR,
            assigned_size=SpotSizeType.REGULAR,
            issued_by=self.attendant,
        )
        # 59 minutes ago -> 1 hour -> $10 owed
        self.ticket.entry_time = timezone.now() - timedelta(minutes=59)
        self.ticket.save()

    def test_ticket_scan_success(self):
        res = self.client.post("/api/v1/tickets/scan/", {"ticket_code": self.ticket.ticket_code}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["amount_owed"], 10.00)
        self.assertEqual(res.data["duration_hours"], 1)

    def test_ticket_scan_not_found(self):
        res = self.client.post("/api/v1/tickets/scan/", {"ticket_code": "INVALID123"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("apps.payments.services.InventoryService.attempt_release")
    def test_payment_process_success(self, mock_release):
        mock_release.return_value = True

        res = self.client.post("/api/v1/payments/", {
            "ticket_id": self.ticket.ticket_code,
            "amount_paid": "10.00",
            "method": "CASH"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("payment_id", res.data)
        
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.PAID)

    def test_payment_process_insufficient(self):
        res = self.client.post("/api/v1/payments/", {
            "ticket_id": self.ticket.ticket_code,
            "amount_paid": "5.00",
            "method": "CASH"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Insufficient payment", res.data["error"])


# ──────────────────────────────────────────────────────────────────
# Admin Reports and Settings Tests
# ──────────────────────────────────────────────────────────────────

class AdminPaymentsAPITest(TestCase):
    def setUp(self):
        self.admin = make_admin()
        self.attendant = make_attendant(username="att2")
        self.admin_client = make_client(self.admin)
        self.att_client = make_client(self.attendant)

        self.rule = PricingRule.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            spot_size=SpotSizeType.COMPACT,
            hourly_rate=Decimal("5.00"),
            max_daily_rate=Decimal("25.00"),
            is_active=True,
            time_start=datetime.time(0, 0),
            time_end=datetime.time(23, 59),
        )

    def test_attendant_cannot_update_pricing(self):
        res = self.att_client.patch(f"/api/v1/pricing-rules/{self.rule.id}/", {"hourly_rate": "6.00"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_update_pricing(self):
        res = self.admin_client.patch(f"/api/v1/pricing-rules/{self.rule.id}/", {"hourly_rate": "7.50"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        
        self.rule.refresh_from_db()
        self.assertEqual(self.rule.hourly_rate, Decimal("7.50"))

        # Verify audit log
        log = AuditLog.objects.filter(action_type=AuditActionType.PRICE_CHANGE).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.details["new"]["hourly_rate"], "7.50")

    def test_revenue_report_access(self):
        res = self.att_client.get("/api/v1/reports/revenue/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.admin_client.get("/api/v1/reports/revenue/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_peak_hours_report_access(self):
        res = self.att_client.get("/api/v1/reports/peak-hours/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.admin_client.get("/api/v1/reports/peak-hours/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
