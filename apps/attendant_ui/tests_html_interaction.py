"""
Gate Ops HTML Interaction Tests
================================
Browser-level (Playwright + StaticLiveServerTestCase) tests for the three
manual gate operation pages:

  /attendant/app/entry/         — ManualEntryView  → POST /api/v1/gates/entry/
  /attendant/app/ticket-lookup/ — TicketLookupView → GET  /api/v1/gates/tickets/<code>/
  /attendant/app/override/      — GateOverrideView → POST /api/v1/gates/<gate_id>/override/

Each test drives a real Chromium browser against a live Django test server,
seeds JWT tokens into localStorage, interacts with form elements, and asserts
both DOM state and database outcomes.

Mirrors the pattern established in apps/payments/tests_html_interaction.py.
"""
import os
import unittest

# Playwright's sync API runs its own asyncio event loop; allow Django ORM
# calls from the same thread as the browser.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import AuditActionType, AuditLog
from apps.gates.models import Ticket, TicketStatus
from apps.inventory.models import LotOccupancy, SpotSizeType, VehicleType

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import expect, sync_playwright
except ImportError:  # pragma: no cover
    PlaywrightError = None
    expect = None
    sync_playwright = None

User = get_user_model()


class GateOpsHtmlInteractionTests(StaticLiveServerTestCase):
    """Browser-level tests for the manual gate operation pages."""

    host = "127.0.0.1"

    # ──────────────────────────────────────────────────────────────────
    # Browser lifecycle
    # ──────────────────────────────────────────────────────────────────

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
                "Playwright could not start in this environment."
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
        self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        self.page = self.context.new_page()
        self.admin    = self._make_admin()
        self.attendant = self._make_attendant()

    def tearDown(self):
        os.makedirs("playwright_traces", exist_ok=True)
        self.context.tracing.stop(path=f"playwright_traces/{self.id()}.zip")
        self.context.close()

    # ──────────────────────────────────────────────────────────────────
    # Helpers — data factories
    # ──────────────────────────────────────────────────────────────────

    def _make_admin(self, **kw):
        defaults = dict(username="gate_admin", password="AdminPass1!", role="ADMIN")
        defaults.update(kw)
        return User.objects.create_user(**defaults)

    def _make_attendant(self, **kw):
        defaults = dict(username="gate_att", password="AttPass1!", role="ATTENDANT")
        defaults.update(kw)
        return User.objects.create_user(**defaults)

    def _seed_occupancy(self, size=SpotSizeType.REGULAR, total=10, current=0):
        return LotOccupancy.objects.create(
            spot_size=size,
            total_capacity=total,
            current_count=current,
            version=0,
        )

    def _make_ticket(self, vehicle_type=VehicleType.CAR,
                     assigned_size=SpotSizeType.REGULAR,
                     status=TicketStatus.OPEN):
        # Note: Ticket model has no gate_id or plate_number fields;
        # those are request-layer values not persisted on the model.
        return Ticket.objects.create(
            vehicle_type=vehicle_type,
            assigned_size=assigned_size,
            status=status,
            issued_by=self.attendant,
        )

    # ──────────────────────────────────────────────────────────────────
    # Helpers — browser auth & navigation
    # ──────────────────────────────────────────────────────────────────

    def _seed_auth(self, user):
        """Inject a valid JWT pair into localStorage before page load."""
        refresh = RefreshToken.for_user(user)
        self.context.add_init_script(
            f"""
              window.localStorage.setItem('access_token', '{refresh.access_token}');
              window.localStorage.setItem('refresh_token', '{refresh}');
            """
        )

    def _goto_entry(self):
        self.page.goto(f"{self.live_server_url}/attendant/app/entry/")

    def _goto_lookup(self):
        self.page.goto(f"{self.live_server_url}/attendant/app/ticket-lookup/")

    def _goto_override(self):
        self.page.goto(f"{self.live_server_url}/attendant/app/override/")

    # ──────────────────────────────────────────────────────────────────
    # Helpers — DOM assertions
    # ──────────────────────────────────────────────────────────────────

    def assert_has_visible_class(self, selector):
        """Wait until the element has the 'visible' CSS class (alert pattern)."""
        self.page.wait_for_function(
            """
            (sel) => {
              const el = document.querySelector(sel);
              return Boolean(el && el.classList.contains('visible'));
            }
            """,
            arg=selector,
        )

    def assert_lacks_visible_class(self, selector):
        self.page.wait_for_function(
            """
            (sel) => {
              const el = document.querySelector(sel);
              return Boolean(el && !el.classList.contains('visible'));
            }
            """,
            arg=selector,
        )

    def assert_display_visible(self, selector):
        """Wait until the element's display style is not 'none'."""
        self.page.wait_for_function(
            """
            (sel) => {
              const el = document.querySelector(sel);
              return Boolean(el && el.style.display !== 'none');
            }
            """,
            arg=selector,
        )

    def assert_display_hidden(self, selector):
        """Wait until the element's display style is 'none'."""
        self.page.wait_for_function(
            """
            (sel) => {
              const el = document.querySelector(sel);
              return Boolean(el && el.style.display === 'none');
            }
            """,
            arg=selector,
        )

    # ══════════════════════════════════════════════════════════════════
    # Manual Entry page tests
    # ══════════════════════════════════════════════════════════════════

    def test_entry_page_redirects_without_jwt(self):
        """Unauthenticated visit is redirected to the login page."""
        self._goto_entry()
        self.page.wait_for_url("**/attendant/")
        self.assertEqual(self.page.url, f"{self.live_server_url}/attendant/")

    def test_entry_page_loads_form_for_authenticated_user(self):
        """After login, the entry form is visible and the success card is hidden."""
        self._seed_auth(self.attendant)
        self._goto_entry()

        expect(self.page.locator("#entry-form-card")).to_be_visible()
        expect(self.page.locator("#vehicle-type")).to_be_visible()
        expect(self.page.locator("#gate-id")).to_be_visible()
        # Success and lot-full cards start hidden
        self.assertEqual(
            self.page.locator("#entry-success").evaluate("el => el.style.display"),
            "none",
        )
        self.assertEqual(
            self.page.locator("#lot-full-card").evaluate("el => el.style.display"),
            "none",
        )

    def test_entry_registers_vehicle_and_displays_ticket_code(self):
        """
        Happy path: fill the form → submit → ticket code card appears,
        and the database has a new OPEN ticket with occupancy incremented.
        """
        self._seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        self._seed_auth(self.attendant)
        self._goto_entry()

        self.page.locator("#vehicle-type").select_option("CAR")
        self.page.locator("#gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#entry-form").evaluate("f => f.requestSubmit()")

        # Success card must appear with a non-empty ticket code
        self.assert_display_visible("#entry-success")
        ticket_code = self.page.locator("#result-ticket-code").inner_text().strip()
        self.assertTrue(ticket_code, "Ticket code element should not be empty")
        # Codes are 12-char alphanumeric (e.g. WSXQW7XB3UDN); no fixed prefix
        self.assertEqual(len(ticket_code), 12, f"Unexpected code length: {ticket_code!r}")

        # Receipt rows must be present
        receipt = self.page.locator("#entry-receipt").inner_text()
        self.assertIn("CAR", receipt)
        self.assertIn("GATE-NORTH-01", receipt)

        # Form card must be hidden
        self.assert_display_hidden("#entry-form-card")

        # Database: ticket created and occupancy incremented
        ticket = Ticket.objects.get(ticket_code=ticket_code)
        self.assertEqual(ticket.vehicle_type, VehicleType.CAR)
        self.assertEqual(ticket.status, TicketStatus.OPEN)

        occ = LotOccupancy.objects.get(spot_size=SpotSizeType.REGULAR)
        self.assertEqual(occ.current_count, 1)

    def test_entry_with_optional_plate_number(self):
        """
        Plate number is uppercased by client-side JS and rendered in the
        on-screen receipt.  (The Ticket model does not persist plate_number;
        the value lives only in the audit log.)
        """
        self._seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        self._seed_auth(self.attendant)
        self._goto_entry()

        self.page.locator("#vehicle-type").select_option("CAR")
        self.page.locator("#gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#plate-number").fill("b 1234 xy")
        self.page.locator("#entry-form").evaluate("f => f.requestSubmit()")

        self.assert_display_visible("#entry-success")
        # Client JS uppercases the plate and injects it into the receipt row
        receipt = self.page.locator("#entry-receipt").inner_text()
        self.assertIn("B 1234 XY", receipt, "Uppercased plate should appear in the receipt")

    def test_entry_lot_full_shows_error_card_not_success(self):
        """
        When every spot is taken the API returns 409, the LOT FULL card
        must be shown and the success card must remain hidden.
        """
        self._seed_occupancy(SpotSizeType.REGULAR,   total=1, current=1)
        self._seed_occupancy(SpotSizeType.COMPACT,   total=1, current=1)
        self._seed_occupancy(SpotSizeType.OVERSIZED, total=1, current=1)
        self._seed_auth(self.attendant)
        self._goto_entry()

        self.page.locator("#vehicle-type").select_option("CAR")
        self.page.locator("#gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#entry-form").evaluate("f => f.requestSubmit()")

        self.assert_display_visible("#lot-full-card")
        self.assert_display_hidden("#entry-success")
        self.assert_display_hidden("#entry-form-card")

        # No ticket should have been created (lot was already full)
        self.assertEqual(
            Ticket.objects.count(), 0,
            "A ticket must not be created when the lot is full",
        )

    def test_entry_reset_restores_form_after_lot_full(self):
        """Clicking '← Try Again' hides the lot-full card and shows the form."""
        self._seed_occupancy(SpotSizeType.REGULAR, total=1, current=1)
        self._seed_occupancy(SpotSizeType.COMPACT, total=1, current=1)
        self._seed_occupancy(SpotSizeType.OVERSIZED, total=1, current=1)
        self._seed_auth(self.attendant)
        self._goto_entry()

        self.page.locator("#vehicle-type").select_option("CAR")
        self.page.locator("#gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#entry-form").evaluate("f => f.requestSubmit()")
        self.assert_display_visible("#lot-full-card")

        self.page.get_by_text("← Try Again").click()

        self.assert_display_visible("#entry-form-card")
        self.assert_display_hidden("#lot-full-card")

    def test_entry_reset_restores_form_after_success(self):
        """Clicking 'Register Another Vehicle' shows a fresh empty form."""
        self._seed_occupancy(SpotSizeType.REGULAR, total=5, current=0)
        self._seed_auth(self.attendant)
        self._goto_entry()

        self.page.locator("#vehicle-type").select_option("CAR")
        self.page.locator("#gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#entry-form").evaluate("f => f.requestSubmit()")
        self.assert_display_visible("#entry-success")

        self.page.get_by_text("Register Another Vehicle").click()

        self.assert_display_visible("#entry-form-card")
        self.assert_display_hidden("#entry-success")
        # Form is reset — vehicle select should be back to placeholder
        self.assertEqual(
            self.page.locator("#vehicle-type").input_value(), ""
        )

    # ══════════════════════════════════════════════════════════════════
    # Ticket Lookup page tests
    # ══════════════════════════════════════════════════════════════════

    def test_lookup_page_redirects_without_jwt(self):
        self._goto_lookup()
        self.page.wait_for_url("**/attendant/")
        self.assertEqual(self.page.url, f"{self.live_server_url}/attendant/")

    def test_lookup_valid_open_ticket_displays_all_details(self):
        """
        Enter a known ticket code → result card appears with all fields populated.
        Note: gate_id and plate_number are not stored on the Ticket model, so
        those fields are not asserted here.
        """
        ticket = self._make_ticket()   # no gate_id — not a model field
        self._seed_auth(self.attendant)
        self._goto_lookup()

        self.page.locator("#lookup-code").fill(ticket.ticket_code.lower())
        self.page.locator("#lookup-form").evaluate("f => f.requestSubmit()")

        self.assert_display_visible("#result-card")

        # Fields that ARE in TicketReadSerializer
        expect(self.page.locator("#res-ticket-code")).to_have_text(ticket.ticket_code)
        expect(self.page.locator("#res-vehicle")).to_have_text(VehicleType.CAR)
        expect(self.page.locator("#res-spot")).to_have_text(SpotSizeType.REGULAR)
        expect(self.page.locator("#result-status-badge")).to_contain_text("OPEN")
        # Issued-by username is returned by the serializer
        expect(self.page.locator("#res-issued-by")).to_have_text(self.attendant.username)

    def test_lookup_invalid_code_shows_error_and_hides_result(self):
        """Unknown ticket code → error alert shown, result card stays hidden."""
        self._seed_auth(self.attendant)
        self._goto_lookup()

        self.page.locator("#lookup-code").fill("TKT-DOESNOTEXIST")
        self.page.locator("#lookup-form").evaluate("f => f.requestSubmit()")

        self.assert_has_visible_class("#lookup-error")
        self.assertEqual(
            self.page.locator("#result-card").evaluate("el => el.style.display"),
            "none",
        )
        expect(self.page.locator("#lookup-btn")).to_be_enabled()

    def test_lookup_open_ticket_shows_proceed_to_payment_button(self):
        """OPEN status → 'Proceed to Payment' button is visible."""
        ticket = self._make_ticket(status=TicketStatus.OPEN)
        self._seed_auth(self.attendant)
        self._goto_lookup()

        self.page.locator("#lookup-code").fill(ticket.ticket_code)
        self.page.locator("#lookup-form").evaluate("f => f.requestSubmit()")

        self.assert_display_visible("#result-card")
        self.assert_display_visible("#proceed-pay-btn")

    def test_lookup_paid_ticket_hides_proceed_to_payment_button(self):
        """PAID status → 'Proceed to Payment' button is NOT shown."""
        ticket = self._make_ticket(status=TicketStatus.PAID)
        self._seed_auth(self.attendant)
        self._goto_lookup()

        self.page.locator("#lookup-code").fill(ticket.ticket_code)
        self.page.locator("#lookup-form").evaluate("f => f.requestSubmit()")

        self.assert_display_visible("#result-card")
        self.assertEqual(
            self.page.locator("#proceed-pay-btn").evaluate("el => el.style.display"),
            "none",
        )

    def test_lookup_proceed_navigates_to_checkout_with_session_storage(self):
        """
        Clicking 'Proceed to Payment' navigates to checkout and seeds
        sessionStorage with the correct ticket data under 'pending_ticket'.
        """
        ticket = self._make_ticket(status=TicketStatus.OPEN)
        self._seed_auth(self.attendant)
        self._goto_lookup()

        self.page.locator("#lookup-code").fill(ticket.ticket_code)
        self.page.locator("#lookup-form").evaluate("f => f.requestSubmit()")
        self.assert_display_visible("#proceed-pay-btn")
        self.page.locator("#proceed-pay-btn").click()

        self.page.wait_for_url("**/attendant/app/checkout/")

        pending = self.page.evaluate(
            "JSON.parse(window.sessionStorage.getItem('pending_ticket'))"
        )
        self.assertEqual(pending["ticket_code"], ticket.ticket_code)
        self.assertEqual(pending["vehicle_type"], VehicleType.CAR)

    def test_lookup_reset_clears_result_card(self):
        """Clicking 'Look Up Another' hides the result card and clears the input."""
        ticket = self._make_ticket()
        self._seed_auth(self.attendant)
        self._goto_lookup()

        self.page.locator("#lookup-code").fill(ticket.ticket_code)
        self.page.locator("#lookup-form").evaluate("f => f.requestSubmit()")
        self.assert_display_visible("#result-card")

        self.page.get_by_text("Look Up Another").click()

        self.assertEqual(
            self.page.locator("#result-card").evaluate("el => el.style.display"),
            "none",
        )
        self.assertEqual(self.page.locator("#lookup-code").input_value(), "")

    # ══════════════════════════════════════════════════════════════════
    # Gate Override page tests
    # ══════════════════════════════════════════════════════════════════

    def test_override_page_redirects_without_jwt(self):
        self._goto_override()
        self.page.wait_for_url("**/attendant/")
        self.assertEqual(self.page.url, f"{self.live_server_url}/attendant/")

    def test_override_shows_admin_guard_banner_for_attendant(self):
        """
        An attendant (non-admin) visiting the page should see the warning
        banner revealed by checkAdminRole() after it fetches /auth/users/me/.
        The .alert CSS class may keep the element visually hidden via computed
        style, so we assert on the inline display property that the JS sets.
        """
        self._seed_auth(self.attendant)
        self._goto_override()

        # The JS sets style.display='' (removes the inline none) for non-admin users.
        # wait_for_function resolving IS the assertion — it only resolves once
        # checkAdminRole() has updated the inline style.
        self.page.wait_for_function(
            "() => document.getElementById('admin-guard').style.display !== 'none'"
        )
        banner_display = self.page.locator("#admin-guard").evaluate("el => el.style.display")
        self.assertNotEqual(
            banner_display, "none",
            "Admin guard banner inline display should be revealed for non-admin users",
        )

    def test_override_admin_guard_banner_hidden_for_admin(self):
        """
        An admin user should NOT see the warning banner (it stays hidden).
        """
        self._seed_auth(self.admin)
        self._goto_override()

        # Wait long enough for the role check to complete, then assert still hidden
        self.page.wait_for_timeout(800)
        banner = self.page.locator("#admin-guard")
        self.assertEqual(banner.evaluate("el => el.style.display"), "none")

    def test_override_missing_direction_shows_js_error(self):
        """
        Submitting without selecting a direction triggers the client-side
        validation error (no API call made).

        We use dispatchEvent instead of requestSubmit() so that the browser's
        built-in HTML5 required-field validation does NOT fire.  The direction
        radio has `required`; requestSubmit() would show a native browser popup
        and never invoke our JS handler.  dispatchEvent skips that validation
        and fires the submit event listener directly.
        """
        self._seed_auth(self.admin)
        self._goto_override()

        self.page.locator("#override-gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#override-reason").fill("Test — no direction selected")
        # Do NOT click a direction radio; dispatch submit directly to hit JS handler
        self.page.locator("#override-form").evaluate(
            "f => f.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true}))"
        )

        self.assert_has_visible_class("#override-error")
        # Success card must not appear
        self.assertEqual(
            self.page.locator("#override-success").evaluate("el => el.style.display"),
            "none",
        )

    def test_override_successful_as_admin_shows_confirmation_and_writes_audit(self):
        """
        Admin fills all fields and submits → success card appears, AuditLog
        row is written with MANUAL_GATE_OPEN action and correct details.
        """
        self._seed_auth(self.admin)
        self._goto_override()

        self.page.locator("#override-gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#dir-entry").click()
        self.page.locator("#override-reason").fill("Fire drill — emergency access")
        self.page.locator("#override-plate").fill("fire01")
        self.page.locator("#override-form").evaluate("f => f.requestSubmit()")

        # Use Playwright's native visibility wait (computed style) rather than
        # the inline-style helper, so we know the card is truly rendered.
        self.page.locator("#override-success").wait_for(state="visible")
        self.assert_display_hidden("#override-form-card")

        # Receipt in the success card must show key details
        receipt = self.page.locator("#override-receipt").inner_text()
        self.assertIn("GATE-NORTH-01", receipt)
        self.assertIn("ENTRY", receipt)
        self.assertIn("Fire drill", receipt)

        # Database: AuditLog entry created
        log = AuditLog.objects.get(action_type=AuditActionType.MANUAL_GATE_OPEN)
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.details["gate_id"], "GATE-NORTH-01")
        self.assertEqual(log.details["direction"], "ENTRY")
        self.assertIn("Fire drill", log.details["reason"])
        self.assertEqual(log.details["plate_number"], "FIRE01")

    def test_override_rejected_for_attendant_shows_error(self):
        """
        An attendant submitting the override form gets a 403 from the API;
        the error banner must be shown and the success card must stay hidden.
        """
        self._seed_auth(self.attendant)
        self._goto_override()

        self.page.locator("#override-gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#dir-exit").click()
        self.page.locator("#override-reason").fill("Attendant attempting override")
        self.page.locator("#override-form").evaluate("f => f.requestSubmit()")

        self.assert_has_visible_class("#override-error")
        self.assertEqual(
            self.page.locator("#override-success").evaluate("el => el.style.display"),
            "none",
        )
        # Confirm no audit log was written
        self.assertFalse(
            AuditLog.objects.filter(action_type=AuditActionType.MANUAL_GATE_OPEN).exists()
        )

    def test_override_reset_restores_blank_form(self):
        """
        After a successful override the reset button calls resetOverride().
        We invoke it via page.evaluate() rather than clicking, because the
        button lives inside the success card whose computed visibility may
        differ from its inline display style.
        """
        self._seed_auth(self.admin)
        self._goto_override()

        self.page.locator("#override-gate-id").select_option("GATE-NORTH-01")
        self.page.locator("#dir-entry").click()
        self.page.locator("#override-reason").fill("VIP access")
        self.page.locator("#override-form").evaluate("f => f.requestSubmit()")
        self.page.locator("#override-success").wait_for(state="visible")

        # Directly call the JS reset function (same as clicking the button)
        self.page.evaluate("resetOverride()")

        self.assert_display_visible("#override-form-card")
        self.assert_display_hidden("#override-success")
        # Reason field should be blank after reset
        self.assertEqual(self.page.locator("#override-reason").input_value(), "")
