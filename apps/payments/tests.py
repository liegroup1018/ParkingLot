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
from freezegun import freeze_time
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
from apps.payments.models import Payment, PaymentStatus, PricingRule
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

@freeze_time("2026-05-08 12:00:00")
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
        # 2.5 hours should round up to 3 hours
        self.ticket.entry_time = timezone.now() - timedelta(hours=2, minutes=30)
        self.ticket.save()

        fee = PricingService.calculate_fee(self.ticket)
        self.assertEqual(fee["duration_hours"], 3)
        self.assertEqual(fee["amount_owed"], Decimal("30.00"))

    def test_calculate_fee_hits_daily_cap(self):
        # 6 hours = 60 dollars, but daily cap is 50
        self.ticket.entry_time = timezone.now() - timedelta(hours=6)
        self.ticket.save()

        fee = PricingService.calculate_fee(self.ticket)
        self.assertEqual(fee["duration_hours"], 6)
        self.assertEqual(fee["amount_owed"], Decimal("50.00"))

    def test_calculate_fee_multi_day(self):
        # 25 hours = 2 days, 2 days cap = 100
        self.ticket.entry_time = timezone.now() - timedelta(hours=25)
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

    def test_calculate_fee_uses_rule_matching_current_time_window(self):
        self.rule.time_start = datetime.time(0, 0)
        self.rule.time_end = datetime.time(1, 0)
        self.rule.hourly_rate = Decimal("99.00")
        self.rule.max_daily_rate = Decimal("500.00")
        self.rule.save()
        PricingRule.objects.create(
            vehicle_type=VehicleType.CAR,
            spot_size=SpotSizeType.REGULAR,
            hourly_rate=Decimal("12.00"),
            max_daily_rate=Decimal("50.00"),
            is_active=True,
            time_start=datetime.time(8, 0),
            time_end=datetime.time(18, 0),
        )
        self.ticket.entry_time = timezone.now() - timedelta(hours=2)
        self.ticket.save()

        fee = PricingService.calculate_fee(self.ticket)

        self.assertEqual(fee["hourly_rate"], Decimal("12.00"))
        self.assertEqual(fee["amount_owed"], Decimal("24.00"))

    @freeze_time("2026-05-08 23:30:00")
    def test_calculate_fee_supports_overnight_time_window(self):
        self.rule.time_start = datetime.time(0, 0)
        self.rule.time_end = datetime.time(1, 0)
        self.rule.hourly_rate = Decimal("99.00")
        self.rule.max_daily_rate = Decimal("500.00")
        self.rule.save()
        PricingRule.objects.create(
            vehicle_type=VehicleType.CAR,
            spot_size=SpotSizeType.REGULAR,
            hourly_rate=Decimal("8.00"),
            max_daily_rate=Decimal("40.00"),
            is_active=True,
            time_start=datetime.time(22, 0),
            time_end=datetime.time(2, 0),
        )
        self.ticket.entry_time = timezone.now() - timedelta(hours=3)
        self.ticket.save()

        fee = PricingService.calculate_fee(self.ticket)

        self.assertEqual(fee["hourly_rate"], Decimal("8.00"))
        self.assertEqual(fee["amount_owed"], Decimal("24.00"))


@freeze_time("2026-05-08 12:00:00")
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
        # Entry 2 hours ago -> fee $20
        self.ticket.entry_time = timezone.now() - timedelta(hours=2)
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

    def test_process_payment_converts_pricing_error_to_payment_error(self):
        PricingRule.objects.all().delete()

        with self.assertRaises(PaymentError) as context:
            PaymentService.process_payment(
                ticket=self.ticket,
                amount_paid=Decimal("20.00"),
                method="CASH",
                processed_by=self.attendant,
            )

        self.assertIn("No active pricing rule", str(context.exception))

    @patch("apps.payments.services.time.sleep")
    @patch("apps.payments.services.InventoryService.attempt_release")
    def test_process_payment_retries_inventory_release_until_success(self, mock_release, mock_sleep):
        mock_release.side_effect = [False, False, True]

        PaymentService.process_payment(
            ticket=self.ticket,
            amount_paid=Decimal("20.00"),
            method="CASH",
            processed_by=self.attendant,
        )

        self.assertEqual(mock_release.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch("apps.payments.services.time.sleep")
    @patch("apps.payments.services.InventoryService.attempt_release")
    def test_process_payment_logs_release_failure_after_retries(self, mock_release, mock_sleep):
        mock_release.return_value = False

        with self.assertLogs("apps.payments.services", level="WARNING") as logs:
            PaymentService.process_payment(
                ticket=self.ticket,
                amount_paid=Decimal("20.00"),
                method="CASH",
                processed_by=self.attendant,
            )

        self.assertEqual(mock_release.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 3)
        self.assertIn("OCC release failed after 3 retries", logs.output[0])

    @patch("apps.payments.services.InventoryService.attempt_release")
    def test_process_lost_ticket_charges_single_daily_maximum(self, mock_release):
        mock_release.return_value = True
        self.ticket.status = TicketStatus.LOST
        self.ticket.entry_time = timezone.now() - timedelta(days=7)
        self.ticket.save()

        payment = PaymentService.process_payment(
            ticket=self.ticket,
            amount_paid=Decimal("50.00"),
            method="CASH",
            processed_by=self.attendant,
        )

        self.assertEqual(payment.amount, Decimal("50.00"))
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.PAID)


# ──────────────────────────────────────────────────────────────────
# API Views Tests
# ──────────────────────────────────────────────────────────────────

@freeze_time("2026-05-08 12:00:00")
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
        # 1 hour ago -> $10 owed
        self.ticket.entry_time = timezone.now() - timedelta(hours=1)
        self.ticket.save()

    def test_ticket_scan_success(self):
        res = self.client.post("/api/v1/tickets/scan/", {"ticket_code": self.ticket.ticket_code}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["amount_owed"], 10.00)
        self.assertEqual(res.data["duration_hours"], 1)

    def test_ticket_scan_not_found(self):
        res = self.client.post("/api/v1/tickets/scan/", {"ticket_code": "INVALID123"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_ticket_scan_requires_authentication(self):
        client = APIClient()
        res = client.post("/api/v1/tickets/scan/", {"ticket_code": self.ticket.ticket_code}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ticket_scan_rejects_paid_ticket(self):
        self.ticket.status = TicketStatus.PAID
        self.ticket.save()

        res = self.client.post("/api/v1/tickets/scan/", {"ticket_code": self.ticket.ticket_code}, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not OPEN", res.data["error"])

    def test_ticket_scan_reports_missing_pricing_rule(self):
        PricingRule.objects.all().delete()

        res = self.client.post("/api/v1/tickets/scan/", {"ticket_code": self.ticket.ticket_code}, format="json")

        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("No active pricing rule", res.data["error"])

    def test_lost_ticket_create_success(self):
        res = self.client.post("/api/v1/tickets/lost/", {"vehicle_type": VehicleType.CAR}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("ticket_code", res.data)
        self.assertEqual(res.data["vehicle_type"], VehicleType.CAR)
        self.assertEqual(res.data["assigned_size"], SpotSizeType.REGULAR)
        self.assertEqual(res.data["amount_owed"], 50.00) # max daily rate
        
        ticket = Ticket.objects.get(ticket_code=res.data["ticket_code"])
        self.assertEqual(ticket.status, TicketStatus.LOST)

    def test_lost_ticket_requires_authentication(self):
        client = APIClient()
        res = client.post("/api/v1/tickets/lost/", {"vehicle_type": VehicleType.CAR}, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

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

    def test_payment_process_requires_authentication(self):
        client = APIClient()
        res = client.post("/api/v1/payments/", {
            "ticket_id": self.ticket.ticket_code,
            "amount_paid": "10.00",
            "method": "CASH"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_payment_process_not_found(self):
        res = self.client.post("/api/v1/payments/", {
            "ticket_id": "INVALID123",
            "amount_paid": "10.00",
            "method": "CASH"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_payment_process_rejects_paid_ticket(self):
        self.ticket.status = TicketStatus.PAID
        self.ticket.save()

        res = self.client.post("/api/v1/payments/", {
            "ticket_id": self.ticket.ticket_code,
            "amount_paid": "10.00",
            "method": "CASH"
        }, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot be paid again", res.data["error"])

    @patch("apps.payments.services.InventoryService.attempt_release")
    def test_payment_process_accepts_lost_ticket_at_daily_maximum(self, mock_release):
        mock_release.return_value = True
        self.ticket.status = TicketStatus.LOST
        self.ticket.entry_time = timezone.now() - timedelta(days=7)
        self.ticket.save()

        res = self.client.post("/api/v1/payments/", {
            "ticket_id": self.ticket.ticket_code,
            "amount_paid": "50.00",
            "method": "CASH"
        }, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.PAID)

    def test_payment_process_rejects_invalid_method(self):
        res = self.client.post("/api/v1/payments/", {
            "ticket_id": self.ticket.ticket_code,
            "amount_paid": "10.00",
            "method": "CHECK"
        }, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("method", res.data["error"]["message"])

    @patch("apps.payments.services.InventoryService.attempt_release")
    def test_payment_process_accepts_digital_methods(self, mock_release):
        mock_release.return_value = True

        for method in ("CREDIT", "MOBILE"):
            with self.subTest(method=method):
                ticket = Ticket.objects.create(
                    vehicle_type=VehicleType.CAR,
                    assigned_size=SpotSizeType.REGULAR,
                    issued_by=self.attendant,
                )
                ticket.entry_time = timezone.now() - timedelta(hours=1)
                ticket.save()

                res = self.client.post("/api/v1/payments/", {
                    "ticket_id": ticket.ticket_code,
                    "amount_paid": "10.00",
                    "method": method
                }, format="json")

                self.assertEqual(res.status_code, status.HTTP_201_CREATED)
                self.assertTrue(Payment.objects.filter(ticket=ticket, payment_method=method).exists())


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

    def test_pricing_rule_read_requires_authentication(self):
        res = APIClient().get(f"/api/v1/pricing-rules/{self.rule.id}/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_read_pricing_rule(self):
        res = self.att_client.get(f"/api/v1/pricing-rules/{self.rule.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["hourly_rate"], "5.00")

    def test_pricing_update_validation_blocks_negative_rates(self):
        res = self.admin_client.patch(f"/api/v1/pricing-rules/{self.rule.id}/", {"hourly_rate": "-1.00"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("hourly_rate", res.data["error"]["message"])

    def test_revenue_report_access(self):
        res = self.att_client.get("/api/v1/reports/revenue/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.admin_client.get("/api/v1/reports/revenue/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_revenue_report_aggregates_successful_payments_by_date(self):
        ticket1 = Ticket.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            assigned_size=SpotSizeType.COMPACT,
            issued_by=self.attendant,
        )
        ticket2 = Ticket.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            assigned_size=SpotSizeType.COMPACT,
            issued_by=self.attendant,
        )
        ticket3 = Ticket.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            assigned_size=SpotSizeType.COMPACT,
            issued_by=self.attendant,
        )
        payment1 = Payment.objects.create(
            ticket=ticket1,
            processed_by=self.attendant,
            amount=Decimal("10.00"),
            payment_method="CASH",
            status=PaymentStatus.SUCCESS,
        )
        payment2 = Payment.objects.create(
            ticket=ticket2,
            processed_by=self.attendant,
            amount=Decimal("15.50"),
            payment_method="CREDIT",
            status=PaymentStatus.SUCCESS,
        )
        payment3 = Payment.objects.create(
            ticket=ticket3,
            processed_by=self.attendant,
            amount=Decimal("99.00"),
            payment_method="MOBILE",
            status=PaymentStatus.FAILED,
        )
        Payment.objects.filter(id=payment1.id).update(payment_time=timezone.datetime(2026, 5, 7, 10, tzinfo=datetime.timezone.utc))
        Payment.objects.filter(id=payment2.id).update(payment_time=timezone.datetime(2026, 5, 7, 12, tzinfo=datetime.timezone.utc))
        Payment.objects.filter(id=payment3.id).update(payment_time=timezone.datetime(2026, 5, 7, 13, tzinfo=datetime.timezone.utc))

        res = self.admin_client.get("/api/v1/reports/revenue/?start_date=2026-05-07&end_date=2026-05-07")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [{"date": "2026-05-07", "total_revenue": 25.5, "payment_count": 2}])

    def test_peak_hours_report_access(self):
        res = self.att_client.get("/api/v1/reports/peak-hours/")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

        res = self.admin_client.get("/api/v1/reports/peak-hours/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_peak_hours_report_groups_ticket_entries_for_requested_date(self):
        ticket1 = Ticket.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            assigned_size=SpotSizeType.COMPACT,
            issued_by=self.attendant,
        )
        ticket2 = Ticket.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            assigned_size=SpotSizeType.COMPACT,
            issued_by=self.attendant,
        )
        ticket3 = Ticket.objects.create(
            vehicle_type=VehicleType.MOTORCYCLE,
            assigned_size=SpotSizeType.COMPACT,
            issued_by=self.attendant,
        )
        Ticket.objects.filter(id=ticket1.id).update(entry_time=timezone.datetime(2026, 5, 7, 8, 15, tzinfo=datetime.timezone.utc))
        Ticket.objects.filter(id=ticket2.id).update(entry_time=timezone.datetime(2026, 5, 7, 8, 45, tzinfo=datetime.timezone.utc))
        Ticket.objects.filter(id=ticket3.id).update(entry_time=timezone.datetime(2026, 5, 8, 9, 0, tzinfo=datetime.timezone.utc))

        res = self.admin_client.get("/api/v1/reports/peak-hours/?date=2026-05-07")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [{"hour": 8, "entry_count": 2}])
