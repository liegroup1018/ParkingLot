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
