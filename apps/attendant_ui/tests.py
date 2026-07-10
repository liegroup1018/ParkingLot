from django.test import SimpleTestCase
from django.urls import reverse


class AttendantRouteDesignTests(SimpleTestCase):
    def test_attendant_root_uses_entry_login_page(self):
        path = reverse("attendant:entry")
        response = self.client.get(path)

        self.assertEqual(path, "/attendant/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendant/login.html")

    def test_attendant_login_alias_uses_login_page(self):
        path = reverse("attendant:login")
        response = self.client.get(path)

        self.assertEqual(path, "/attendant/login/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendant/login.html")

    def test_dashboard_is_moved_under_app_namespace(self):
        path = reverse("attendant:dashboard")
        response = self.client.get(path)

        self.assertEqual(path, "/attendant/app/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendant/dashboard.html")

    def test_dashboard_shell_exposes_logout_action(self):
        response = self.client.get(reverse("attendant:dashboard"))

        self.assertContains(response, "Sign Out")
        self.assertContains(response, "handleLogout")

    def test_scan_is_moved_under_app_namespace(self):
        path = reverse("attendant:scan_ticket")
        response = self.client.get(path)

        self.assertEqual(path, "/attendant/app/scan/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendant/scan_ticket.html")

    def test_checkout_is_moved_under_app_namespace(self):
        path = reverse("attendant:checkout")
        response = self.client.get(path)

        self.assertEqual(path, "/attendant/app/checkout/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "attendant/checkout.html")


# ──────────────────────────────────────────────────────────────────
# Manual Gate Operation pages
# ──────────────────────────────────────────────────────────────────

class ManualEntryViewTests(SimpleTestCase):
    """
    Tests for the Manual Entry shell page (/attendant/app/entry/).

    This view only renders a template; the underlying POST /api/v1/gates/entry/
    API is tested in apps/gates/tests.py::GateEntryAPITest.
    """

    def setUp(self):
        self.url = reverse("attendant:manual_entry")
        self.response = self.client.get(self.url)

    def test_resolves_to_correct_path(self):
        self.assertEqual(self.url, "/attendant/app/entry/")

    def test_returns_200(self):
        self.assertEqual(self.response.status_code, 200)

    def test_uses_correct_template(self):
        self.assertTemplateUsed(self.response, "attendant/manual_entry.html")

    def test_extends_base_template(self):
        # base.html is always in the template chain
        self.assertTemplateUsed(self.response, "base.html")

    def test_page_title_present(self):
        self.assertContains(self.response, "Manual Entry")

    def test_vehicle_type_select_rendered(self):
        # All three vehicle type options must be present
        self.assertContains(self.response, 'value="CAR"')
        self.assertContains(self.response, 'value="MOTORCYCLE"')
        self.assertContains(self.response, 'value="TRUCK"')

    def test_gate_id_select_rendered(self):
        self.assertContains(self.response, "GATE-NORTH-01")

    def test_plate_number_field_rendered(self):
        self.assertContains(self.response, 'id="plate-number"')

    def test_submit_button_rendered(self):
        self.assertContains(self.response, "Register Entry")

    def test_js_posts_to_gates_entry_api(self):
        # The template must reference the correct API path
        self.assertContains(self.response, "/gates/entry/")

    def test_lot_full_card_present_but_hidden(self):
        # The LOT FULL card must exist in the DOM (hidden initially)
        self.assertContains(self.response, 'id="lot-full-card"')

    def test_success_card_present_but_hidden(self):
        self.assertContains(self.response, 'id="entry-success"')

    def test_result_ticket_code_element_present(self):
        # The element that displays the generated ticket code must exist
        self.assertContains(self.response, 'id="result-ticket-code"')

    def test_sidebar_includes_gate_ops_section(self):
        self.assertContains(self.response, "Gate Ops")

    def test_manual_entry_nav_link_active(self):
        # active_page='entry' means this nav item should have the active class
        self.assertContains(self.response, 'class="active"')


class TicketLookupViewTests(SimpleTestCase):
    """
    Tests for the Ticket Lookup shell page (/attendant/app/ticket-lookup/).

    The underlying GET /api/v1/gates/tickets/<code>/ API is tested in
    apps/gates/tests.py::TicketDetailAPITest.
    """

    def setUp(self):
        self.url = reverse("attendant:ticket_lookup")
        self.response = self.client.get(self.url)

    def test_resolves_to_correct_path(self):
        self.assertEqual(self.url, "/attendant/app/ticket-lookup/")

    def test_returns_200(self):
        self.assertEqual(self.response.status_code, 200)

    def test_uses_correct_template(self):
        self.assertTemplateUsed(self.response, "attendant/ticket_lookup.html")

    def test_extends_base_template(self):
        self.assertTemplateUsed(self.response, "base.html")

    def test_page_title_present(self):
        self.assertContains(self.response, "Ticket Lookup")

    def test_ticket_code_input_rendered(self):
        self.assertContains(self.response, 'id="lookup-code"')

    def test_submit_button_rendered(self):
        self.assertContains(self.response, "Look Up Ticket")

    def test_result_card_present_but_hidden(self):
        self.assertContains(self.response, 'id="result-card"')

    def test_all_detail_fields_present(self):
        for field_id in (
            "res-ticket-code", "res-vehicle", "res-spot",
            "res-plate", "res-gate", "res-entry", "res-exit",
        ):
            with self.subTest(field=field_id):
                self.assertContains(self.response, f'id="{field_id}"')

    def test_proceed_to_payment_button_present(self):
        # Button exists in DOM (JS controls its visibility)
        self.assertContains(self.response, 'id="proceed-pay-btn"')

    def test_js_calls_gates_tickets_api(self):
        self.assertContains(self.response, "/gates/tickets/")

    def test_js_writes_to_session_storage_for_checkout(self):
        # Lookup page must use the same sessionStorage key as checkout.html
        self.assertContains(self.response, "pending_ticket")
        self.assertContains(self.response, "proceedToCheckout")

    def test_js_encodes_ticket_code_in_url(self):
        self.assertContains(self.response, "encodeURIComponent")

    def test_sidebar_includes_gate_ops_section(self):
        self.assertContains(self.response, "Gate Ops")


class GateOverrideViewTests(SimpleTestCase):
    """
    Tests for the Gate Override shell page (/attendant/app/override/).

    The underlying POST /api/v1/gates/<gate_id>/override/ API is tested in
    apps/gates/tests.py::GateOverrideAPITest.
    Authorization (IsAdminRole) is enforced by DRF on the API, not here.
    """

    def setUp(self):
        self.url = reverse("attendant:gate_override")
        self.response = self.client.get(self.url)

    def test_resolves_to_correct_path(self):
        self.assertEqual(self.url, "/attendant/app/override/")

    def test_returns_200(self):
        self.assertEqual(self.response.status_code, 200)

    def test_uses_correct_template(self):
        self.assertTemplateUsed(self.response, "attendant/gate_override.html")

    def test_extends_base_template(self):
        self.assertTemplateUsed(self.response, "base.html")

    def test_page_title_present(self):
        self.assertContains(self.response, "Gate Override")

    def test_gate_id_select_rendered(self):
        self.assertContains(self.response, 'id="override-gate-id"')
        self.assertContains(self.response, "GATE-NORTH-01")

    def test_direction_radios_rendered(self):
        self.assertContains(self.response, 'value="ENTRY"')
        self.assertContains(self.response, 'value="EXIT"')

    def test_reason_textarea_rendered(self):
        self.assertContains(self.response, 'id="override-reason"')

    def test_reason_field_is_required(self):
        self.assertContains(self.response, 'required')

    def test_plate_number_field_rendered(self):
        self.assertContains(self.response, 'id="override-plate"')

    def test_submit_button_rendered(self):
        self.assertContains(self.response, "Open Gate Now")

    def test_admin_guard_banner_present_in_dom(self):
        # The non-admin warning banner must exist (JS controls its visibility)
        self.assertContains(self.response, 'id="admin-guard"')

    def test_destructive_warning_banner_present(self):
        # Inline safety warning about immediate physical effect must be present
        self.assertContains(self.response, "opens a physical gate")

    def test_audit_log_note_present(self):
        self.assertContains(self.response, "audit log")

    def test_success_card_present_but_hidden(self):
        self.assertContains(self.response, 'id="override-success"')

    def test_js_posts_to_correct_override_api_path(self):
        # Gate ID is a URL path param: /gates/<gate_id>/override/
        self.assertContains(self.response, "/override/")
        self.assertContains(self.response, "encodeURIComponent")

    def test_js_check_admin_role_function_present(self):
        self.assertContains(self.response, "checkAdminRole")

    def test_network_error_warns_about_manual_verification(self):
        # Safety-critical: error message must tell admin to verify gate state manually
        self.assertContains(self.response, "verify manually")

    def test_sidebar_override_link_hidden_by_default(self):
        # nav-override li starts hidden; JS reveals it for admins
        self.assertContains(self.response, 'id="nav-override"')
        self.assertContains(self.response, 'style="display:none;"')


# ──────────────────────────────────────────────────────────────────
# Sidebar integration (base.html changes visible on all pages)
# ──────────────────────────────────────────────────────────────────

class SidebarGateOpsTests(SimpleTestCase):
    """
    Verify that the Gate Ops sidebar section is rendered correctly on every
    page that extends base.html.  Spot-checked on dashboard and the three new pages.
    """

    PAGES = [
        "attendant:dashboard",
        "attendant:manual_entry",
        "attendant:ticket_lookup",
        "attendant:gate_override",
    ]

    def _get(self, name):
        return self.client.get(reverse(name))

    def test_gate_ops_label_on_all_pages(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertContains(self._get(name), "Gate Ops")

    def test_manual_entry_nav_link_on_all_pages(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertContains(self._get(name), "/attendant/app/entry/")

    def test_ticket_lookup_nav_link_on_all_pages(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertContains(self._get(name), "/attendant/app/ticket-lookup/")

    def test_override_nav_link_on_all_pages(self):
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertContains(self._get(name), "/attendant/app/override/")

    def test_override_nav_hidden_by_default_on_all_pages(self):
        # The li must start hidden on every page
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertContains(self._get(name), 'id="nav-override"')

    def test_js_reveals_override_for_admin_role(self):
        # The JS condition must be present in base.html
        for name in self.PAGES:
            with self.subTest(page=name):
                self.assertContains(self._get(name), "role === 'ADMIN'")
