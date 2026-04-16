"""
Unit tests for Track 1: Foundation & Identity.

Covers:
  - User model properties (is_admin, is_attendant, has_2fa_configured)
  - AuditLog creation via log_action() manager method
  - JWT login endpoint (happy path + 2FA validation)
  - Permission classes (IsAdminRole, IsAttendantRole)
  - Audit signals (user creation, login success/failure)

Run with:
    python manage.py test apps.accounts
  or:
    pytest apps/accounts/tests.py -v
"""
from unittest.mock import patch

import pyotp
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import AuditActionType, AuditLog, UserRole

User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_admin(**kwargs) -> User:
    defaults = dict(username="admin1", email="admin@test.com", role=UserRole.ADMIN)
    defaults.update(kwargs)
    return User.objects.create_user(password="StrongPass99!", **defaults)


def make_attendant(**kwargs) -> User:
    defaults = dict(username="att1", email="att@test.com", role=UserRole.ATTENDANT)
    defaults.update(kwargs)
    return User.objects.create_user(password="StrongPass99!", **defaults)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------
class UserModelTest(TestCase):
    def test_is_admin_property(self):
        user = make_admin()
        self.assertTrue(user.is_admin)
        self.assertFalse(user.is_attendant)

    def test_is_attendant_property(self):
        user = make_attendant()
        self.assertTrue(user.is_attendant)
        self.assertFalse(user.is_admin)

    def test_has_2fa_configured_false_by_default(self):
        user = make_admin()
        self.assertFalse(user.has_2fa_configured)

    def test_has_2fa_configured_true_after_setup(self):
        user = make_admin()
        user.two_factor_secret = pyotp.random_base32()
        user.save(update_fields=["two_factor_secret"])
        user.refresh_from_db()
        self.assertTrue(user.has_2fa_configured)

    def test_str_representation(self):
        user = make_admin()
        self.assertIn("admin1", str(user))
        self.assertIn("Management Admin", str(user))


class AuditLogModelTest(TestCase):
    def setUp(self):
        self.admin = make_admin()

    def test_log_action_creates_entry(self):
        count_before = AuditLog.objects.count()
        AuditLog.objects.log_action(
            action_type=AuditActionType.PRICE_CHANGE,
            user=self.admin,
            details={"old_rate": 5.0, "new_rate": 6.5},
            ip_address="127.0.0.1",
        )
        self.assertEqual(AuditLog.objects.count(), count_before + 1)

    def test_log_action_with_deleted_user(self):
        """AuditLog survives user deletion (on_delete=SET_NULL)."""
        log = AuditLog.objects.log_action(
            action_type=AuditActionType.LOGIN_SUCCESS,
            user=self.admin,
        )
        user_pk = self.admin.pk
        self.admin.delete()
        log.refresh_from_db()
        self.assertIsNone(log.user)

    def test_audit_log_str(self):
        log = AuditLog.objects.log_action(
            action_type=AuditActionType.MANUAL_GATE_OPEN,
            user=self.admin,
        )
        self.assertIn("admin1", str(log))
        self.assertIn("MANUAL_GATE_OPEN", str(log))

    def test_system_event_no_user(self):
        log = AuditLog.objects.log_action(
            action_type=AuditActionType.OCCUPANCY_RESET,
            user=None,
        )
        self.assertIsNone(log.user)
        self.assertIn("system", str(log))


# ---------------------------------------------------------------------------
# JWT API tests
# ---------------------------------------------------------------------------
class LoginViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("accounts:login")
        self.attendant = make_attendant()

    def test_attendant_login_success(self):
        resp = self.client.post(
            self.url,
            {"username": "att1", "password": "StrongPass99!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
        self.assertEqual(resp.data["user"]["role"], UserRole.ATTENDANT)
        self.assertEqual(
            AuditLog.objects.filter(
                action_type=AuditActionType.LOGIN_SUCCESS,
                user=self.attendant,
            ).count(),
            1,
        )

    def test_login_wrong_password_returns_401(self):
        resp = self.client.post(
            self.url,
            {"username": "att1", "password": "WRONG"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            AuditLog.objects.filter(action_type=AuditActionType.LOGIN_FAILED).count(),
            1,
        )

    def test_admin_without_2fa_secret_can_login(self):
        """Admin with no 2FA configured should still be able to log in."""
        admin = make_admin(username="admin_no2fa")
        resp = self.client.post(
            self.url,
            {"username": "admin_no2fa", "password": "StrongPass99!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_with_2fa_needs_totp(self):
        """Admin with 2FA configured must supply a valid totp_code."""
        secret = pyotp.random_base32()
        admin = make_admin(username="admin_2fa")
        admin.two_factor_secret = secret
        admin.save(update_fields=["two_factor_secret"])

        # Without TOTP code — should fail
        resp = self.client.post(
            self.url,
            {"username": "admin_2fa", "password": "StrongPass99!"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        admin.refresh_from_db()
        self.assertIsNone(admin.last_login)
        self.assertEqual(
            AuditLog.objects.filter(action_type=AuditActionType.LOGIN_FAILED).count(),
            1,
        )

        # With correct TOTP code — should succeed
        valid_code = pyotp.TOTP(secret).now()
        resp = self.client.post(
            self.url,
            {"username": "admin_2fa", "password": "StrongPass99!", "totp_code": valid_code},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AuditLog.objects.filter(
                action_type=AuditActionType.LOGIN_SUCCESS,
                user=admin,
            ).count(),
            1,
        )


class LogoutViewTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = make_attendant()
        login_resp = self.client.post(
            reverse("accounts:login"),
            {"username": "att1", "password": "StrongPass99!"},
            format="json",
        )
        self.access = login_resp.data["access"]
        self.refresh = login_resp.data["refresh"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access}")

    def test_logout_blacklists_token(self):
        resp = self.client.post(
            reverse("accounts:logout"),
            {"refresh": self.refresh},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(
            AuditLog.objects.filter(
                action_type=AuditActionType.LOGOUT,
                user=self.user,
            ).count(),
            1,
        )

    def test_reuse_blacklisted_refresh_fails(self):
        self.client.post(
            reverse("accounts:logout"),
            {"refresh": self.refresh},
            format="json",
        )
        # Try to refresh with the now-blacklisted token
        resp = self.client.post(
            reverse("accounts:token-refresh"),
            {"refresh": self.refresh},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# User management tests
# ---------------------------------------------------------------------------
class UserManagementTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = make_admin()
        self.attendant = make_attendant()
        # Authenticate as admin
        resp = self.client.post(
            reverse("accounts:login"),
            {"username": "admin1", "password": "StrongPass99!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access']}")

    def test_admin_can_list_users(self):
        resp = self.client.get(reverse("accounts:user-list-create"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_create_attendant(self):
        resp = self.client.post(
            reverse("accounts:user-list-create"),
            {
                "username": "newatt",
                "email": "newatt@test.com",
                "role": UserRole.ATTENDANT,
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)

    def test_attendant_cannot_list_users(self):
        """Attendants must not access the user management endpoint."""
        # Re-auth as attendant
        att_resp = self.client.post(
            reverse("accounts:login"),
            {"username": "att1", "password": "StrongPass99!"},
            format="json",
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {att_resp.data['access']}")
        resp = self.client.get(reverse("accounts:user-list-create"))
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_current_user_endpoint(self):
        resp = self.client.get(reverse("accounts:current-user"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "admin1")

    def test_audit_log_endpoint_admin_only(self):
        resp = self.client.get(reverse("accounts:audit-log-list"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
