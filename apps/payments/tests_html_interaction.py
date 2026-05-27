import datetime
import os
import unittest
from decimal import Decimal

# Playwright's sync API runs an asyncio loop in the test thread. These tests are
# still written as synchronous Django tests, so allow ORM setup/assertions here.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.gates.models import Ticket, TicketStatus
from apps.inventory.models import LotOccupancy, SpotSizeType, VehicleType
from apps.payments.models import Payment, PricingRule

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    PlaywrightError = None
    expect = None
    sync_playwright = None


User = get_user_model()

class PaymentsHtmlInteractionTests(StaticLiveServerTestCase):
    """Browser-level tests for the attendant scan and checkout payment pages."""

    host = "127.0.0.1"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if sync_playwright is None:
            raise unittest.SkipTest(
                "Playwright is not installed. Install it with `pip install playwright` "
                "and run `python -m playwright install chromium`."
            )
        if os.name == "nt" and os.environ.get("CODEX_SHELL"):
            raise unittest.SkipTest(
                "Playwright browser tests are skipped in the sandboxed Codex "
                "Windows shell. Run them in a normal local terminal."
            )

        try:
            cls._playwright = sync_playwright().start()
        except Exception as exc:
            raise unittest.SkipTest(
                "Playwright could not start in this environment. If this is a "
                "sandboxed Windows run, execute the tests outside the sandbox."
            ) from exc
        try:
            cls.browser = cls._playwright.chromium.launch(headless=True)
        except PlaywrightError as exc:
            cls._playwright.stop()
            raise unittest.SkipTest(
                "Chromium is not installed for Playwright. Run "
                "`python -m playwright install chromium`."
            ) from exc

    @classmethod
    def tearDownClass(cls):
        browser = getattr(cls, "browser", None)
        if browser:
            browser.close()
        playwright = getattr(cls, "_playwright", None)
        if playwright:
            playwright.stop()
        super().tearDownClass()

    def setUp(self):
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.attendant = self.make_attendant()
        self.rule = self.make_pricing_rule()
        self.ticket = self.make_open_ticket()
        LotOccupancy.objects.create(
            spot_size=SpotSizeType.REGULAR,
            total_capacity=10,
            current_count=1,
            version=0,
        )

    def tearDown(self):
        self.context.close()

    def assert_has_visible_class(self, selector):
        self.page.wait_for_function(
            """
            (selector) => {
              const el = document.querySelector(selector);
              return Boolean(el && el.classList.contains('visible'));
            }
            """,
            selector,
        )

    def assert_lacks_visible_class(self, selector):
        self.page.wait_for_function(
            """
            (selector) => {
              const el = document.querySelector(selector);
              return Boolean(el && !el.classList.contains('visible'));
            }
            """,
            selector,
        )

    def make_attendant(self, **kwargs):
        defaults = {
            "username": "html_attendant",
            "password": "AttPass1!",
            "role": "ATTENDANT",
        }
        defaults.update(kwargs)
        return User.objects.create_user(**defaults)

    def make_pricing_rule(
        self,
        vehicle_type=VehicleType.CAR,
        spot_size=SpotSizeType.REGULAR,
        hourly_rate=Decimal("10.00"),
        max_daily_rate=Decimal("50.00"),
    ):
        return PricingRule.objects.create(
            vehicle_type=vehicle_type,
            spot_size=spot_size,
            hourly_rate=hourly_rate,
            max_daily_rate=max_daily_rate,
            is_active=True,
            time_start=datetime.time(0, 0),
            time_end=datetime.time(23, 59),
        )

    def make_open_ticket(
        self,
        entry_delta=datetime.timedelta(hours=2),
        vehicle_type=VehicleType.CAR,
        assigned_size=SpotSizeType.REGULAR,
        status=TicketStatus.OPEN,
    ):
        ticket = Ticket.objects.create(
            vehicle_type=vehicle_type,
            assigned_size=assigned_size,
            issued_by=self.attendant,
            status=status,
        )
        Ticket.objects.filter(pk=ticket.pk).update(entry_time=timezone.now() - entry_delta)
        ticket.refresh_from_db()
        return ticket

    def seed_auth(self):
        refresh = RefreshToken.for_user(self.attendant)
        self.context.add_init_script(
            """
            ([access, refresh]) => {
              window.localStorage.setItem('access_token', access);
              window.localStorage.setItem('refresh_token', refresh);
            }
            """,
            [str(refresh.access_token), str(refresh)],
        )

    def pending_payload(self, ticket=None, amount="20.00", duration_hours=2):
        ticket = ticket or self.ticket
        return {
            "ticket_id": ticket.id,
            "ticket_code": ticket.ticket_code,
            "vehicle_type": ticket.vehicle_type,
            "assigned_size": ticket.assigned_size,
            "duration_hours": duration_hours,
            "hourly_rate": "10.00",
            "max_daily_rate": "50.00",
            "amount_owed": amount,
        }

    def seed_pending_ticket(self, payload):
        self.context.add_init_script(
            """
            (payload) => {
              window.sessionStorage.setItem('pending_ticket', JSON.stringify(payload));
            }
            """,
            payload,
        )

    def goto_scan(self):
        self.page.goto(f"{self.live_server_url}/attendant/app/scan/")

    def goto_checkout(self):
        self.page.goto(f"{self.live_server_url}/attendant/app/checkout/")

    def submit_valid_scan(self):
        self.seed_auth()
        self.goto_scan()
        self.page.locator("#ticket-code").fill(self.ticket.ticket_code.lower())
        self.page.locator("#scan-form").evaluate("form => form.requestSubmit()")
        self.assert_has_visible_class("#fee-result")

    def test_scan_page_redirects_without_jwt(self):
        self.goto_scan()

        self.page.wait_for_url("**/attendant/")
        self.assertEqual(self.page.url, f"{self.live_server_url}/attendant/")

    def test_scan_valid_ticket_displays_fee_breakdown(self):
        self.submit_valid_scan()

        expect(self.page.locator("#fee-amount")).to_contain_text("20.00")
        details = self.page.locator("#fee-details")
        expect(details).to_contain_text(self.ticket.ticket_code)
        expect(details).to_contain_text(VehicleType.CAR)
        expect(details).to_contain_text("2 hrs")
        expect(details).to_contain_text(SpotSizeType.REGULAR)
        expect(details).to_contain_text("10.00/hr")

    def test_scan_invalid_ticket_displays_error(self):
        self.seed_auth()
        self.goto_scan()
        self.page.locator("#ticket-code").fill("INVALID123")
        self.page.locator("#scan-form").evaluate("form => form.requestSubmit()")

        self.assert_has_visible_class("#scan-error")
        self.assert_lacks_visible_class("#fee-result")
        expect(self.page.locator("#scan-btn")).to_be_enabled()

    def test_scan_proceed_to_checkout_stores_pending_ticket(self):
        self.submit_valid_scan()
        self.page.locator("#proceed-pay-btn").click()

        self.page.wait_for_url("**/attendant/app/checkout/")
        pending = self.page.evaluate("JSON.parse(window.sessionStorage.getItem('pending_ticket'))")
        self.assertEqual(pending["ticket_code"], self.ticket.ticket_code)
        self.assertEqual(pending["vehicle_type"], VehicleType.CAR)
        self.assertEqual(float(pending["amount_owed"]), 20.0)

    def test_checkout_without_pending_ticket_shows_warning(self):
        self.seed_auth()
        self.goto_checkout()

        self.assert_has_visible_class("#no-ticket-alert")
        self.assertEqual(self.page.locator("#checkout-section").evaluate("el => getComputedStyle(el).display"), "none")

    def test_checkout_renders_pending_ticket_summary(self):
        self.seed_auth()
        self.seed_pending_ticket(self.pending_payload())
        self.goto_checkout()

        expect(self.page.locator("#co-ticket-code")).to_have_text(self.ticket.ticket_code)
        expect(self.page.locator("#co-vehicle")).to_have_text(VehicleType.CAR)
        expect(self.page.locator("#co-spot")).to_have_text(SpotSizeType.REGULAR)
        expect(self.page.locator("#co-duration")).to_have_text("2 hrs")
        expect(self.page.locator("#co-total")).to_have_text("CNY 20.00")

    def test_cash_tendered_displays_change(self):
        self.seed_auth()
        self.seed_pending_ticket(self.pending_payload())
        self.goto_checkout()

        self.page.locator("#cash-tendered").fill("50.00")

        expect(self.page.locator("#change-display")).to_be_visible()
        expect(self.page.locator("#change-amount")).to_have_text("CNY 30.00")

    def test_cash_payment_updates_ui_and_backend(self):
        self.seed_auth()
        self.seed_pending_ticket(self.pending_payload())
        self.goto_checkout()

        self.page.locator("#pay-btn").click()

        self.assert_has_visible_class("#gate-open-success")
        receipt = self.page.locator("#success-receipt")
        expect(receipt).to_contain_text(self.ticket.ticket_code)
        expect(receipt).to_contain_text("CASH")
        expect(receipt).to_contain_text("CNY 20.00")
        self.assertIsNone(self.page.evaluate("window.sessionStorage.getItem('pending_ticket')"))

        self.ticket.refresh_from_db()
        occupancy = LotOccupancy.objects.get(spot_size=SpotSizeType.REGULAR)
        payment = Payment.objects.get(ticket=self.ticket)
        self.assertEqual(self.ticket.status, TicketStatus.PAID)
        self.assertEqual(payment.amount, Decimal("20.00"))
        self.assertEqual(payment.payment_method, "CASH")
        self.assertEqual(occupancy.current_count, 0)

    def test_credit_payment_updates_backend_method(self):
        self.seed_auth()
        self.seed_pending_ticket(self.pending_payload())
        self.goto_checkout()

        self.page.locator("#pay-method").select_option("CREDIT")
        self.page.locator("#pay-btn").click()

        self.assert_has_visible_class("#gate-open-success")
        self.assertEqual(Payment.objects.get(ticket=self.ticket).payment_method, "CREDIT")

    def test_mobile_payment_updates_backend_method(self):
        self.seed_auth()
        self.seed_pending_ticket(self.pending_payload())
        self.goto_checkout()

        self.page.locator("#pay-method").select_option("MOBILE")
        self.page.locator("#pay-btn").click()

        self.assert_has_visible_class("#gate-open-success")
        self.assertEqual(Payment.objects.get(ticket=self.ticket).payment_method, "MOBILE")

    def test_payment_failure_shows_error_and_does_not_duplicate_payment(self):
        self.ticket.status = TicketStatus.PAID
        self.ticket.save(update_fields=["status"])
        self.seed_auth()
        self.seed_pending_ticket(self.pending_payload())
        self.goto_checkout()

        self.page.locator("#pay-btn").click()

        self.assert_has_visible_class("#pay-error")
        expect(self.page.locator("#pay-btn")).to_be_enabled()
        self.assert_lacks_visible_class("#gate-open-success")
        self.assertFalse(Payment.objects.filter(ticket=self.ticket).exists())

    def test_lost_ticket_payment_charges_daily_max_if_supported(self):
        lost_ticket = self.make_open_ticket(
            entry_delta=datetime.timedelta(days=7),
            status=TicketStatus.LOST,
        )
        self.seed_auth()
        self.seed_pending_ticket(self.pending_payload(lost_ticket, amount="50.00", duration_hours=168))
        self.goto_checkout()

        self.page.locator("#pay-btn").click()

        self.assert_has_visible_class("#gate-open-success")
        lost_ticket.refresh_from_db()
        payment = Payment.objects.get(ticket=lost_ticket)
        self.assertEqual(lost_ticket.status, TicketStatus.PAID)
        self.assertEqual(payment.amount, Decimal("50.00"))
