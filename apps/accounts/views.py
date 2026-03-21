"""
API views for the accounts app.

Track 1 / Task 1.6 — JWT Authentication endpoints.

Endpoints
---------
POST /api/v1/auth/login/         — Obtain JWT access + refresh tokens
POST /api/v1/auth/refresh/       — Refresh an access token
POST /api/v1/auth/logout/        — Blacklist the refresh token (logout)
POST /api/v1/auth/users/         — Admin: create a new staff account
GET  /api/v1/auth/users/         — Admin: list all staff accounts
GET  /api/v1/auth/users/me/      — Any authenticated user: own profile
GET  /api/v1/auth/audit-logs/    — Admin: read audit trail
POST /api/v1/auth/2fa/setup/     — Admin: generate a TOTP QR URI
POST /api/v1/auth/2fa/verify/    — Admin: verify TOTP code and activate 2FA
"""
import logging

import pyotp
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.models import AuditActionType, AuditLog, UserRole
from apps.accounts.permissions import IsAdminRole
from apps.accounts.serializers import (
    AuditLogSerializer,
    ParkingTokenObtainPairSerializer,
    UserCreateSerializer,
    UserReadSerializer,
)

User = get_user_model()
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JWT — Login & Refresh (Task 1.6)
# ---------------------------------------------------------------------------
@method_decorator(sensitive_post_parameters("password"), name="dispatch")
class LoginView(TokenObtainPairView):
    """
    POST /api/v1/auth/login/

    Authenticate a user and return JWT access + refresh tokens.
    Admin accounts with 2FA configured must also supply `totp_code`.

    Request body
    ------------
    {
        "username": "admin1",
        "password": "s3cr3t!",
        "totp_code": "123456"   # required only for 2FA-enabled admins
    }
    """

    serializer_class = ParkingTokenObtainPairSerializer
    permission_classes = [AllowAny]


class RefreshTokenView(TokenRefreshView):
    """
    POST /api/v1/auth/refresh/

    Exchange a valid refresh token for a new access token.
    """

    permission_classes = [AllowAny]


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/

    Blacklist the supplied refresh token, effectively ending the session.

    Request body
    ------------
    { "refresh": "<refresh_token>" }
    """

    permission_classes = [IsAuthenticated]

    def post(self, request) -> Response:
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"success": False, "error": {"code": "VALIDATION_ERROR", "message": "refresh token is required."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except TokenError as exc:
            return Response(
                {"success": False, "error": {"code": "TOKEN_INVALID", "message": str(exc)}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        logger.info("User %s logged out.", request.user.username)
        return Response({"success": True, "message": "Logged out successfully."}, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# User Management (Admin-only)
# ---------------------------------------------------------------------------
class UserListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/v1/auth/users/  — List all staff users (Admin only).
    POST /api/v1/auth/users/  — Create a new staff account (Admin only).
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return UserCreateSerializer
        return UserReadSerializer

    def get_queryset(self):
        # Optimise: only fetch columns needed for the list view, ordered by username.
        return (
            User.objects.all()
            .only("id", "username", "email", "first_name", "last_name", "role", "is_active", "date_joined", "last_login")
            .order_by("username")
        )

    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        # Audit log is created automatically via the post_save signal.
        return response


class CurrentUserView(generics.RetrieveAPIView):
    """
    GET /api/v1/auth/users/me/

    Returns the authenticated user's own profile.
    All roles may access this endpoint.
    """

    serializer_class = UserReadSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


# ---------------------------------------------------------------------------
# Audit Logs (Admin-only, read-only)
# ---------------------------------------------------------------------------
class AuditLogListView(generics.ListAPIView):
    """
    GET /api/v1/auth/audit-logs/

    Returns paginated audit log entries, newest first.
    Supports optional query-string filters:
      ?action_type=MANUAL_GATE_OPEN
      ?user_id=3
    """

    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        qs = (
            AuditLog.objects.select_related("user")
            .only(
                "id", "action_type", "details", "ip_address", "timestamp",
                "user__username",
            )
            .order_by("-timestamp")
        )
        action_type = self.request.query_params.get("action_type")
        if action_type:
            qs = qs.filter(action_type=action_type)
        user_id = self.request.query_params.get("user_id")
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs


# ---------------------------------------------------------------------------
# 2FA Setup & Verification (Admin-only)
# ---------------------------------------------------------------------------
class TwoFactorSetupView(APIView):
    """
    POST /api/v1/auth/2fa/setup/

    Generates a fresh TOTP secret for the requesting Admin and returns
    a provisioning URI that apps like Google Authenticator can scan as a QR.

    Note: The secret is NOT saved until `2fa/verify/` succeeds.
    The response contains a `provisioning_uri` and the raw `secret`.
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email or user.username,
            issuer_name="ParkingLot Management System",
        )
        # Store temporarily in session; applied only after verify succeeds.
        request.session["pending_2fa_secret"] = secret
        return Response(
            {
                "success": True,
                "provisioning_uri": provisioning_uri,
                "secret": secret,              # raw secret for manual entry
                "message": "Scan the provisioning URI with your authenticator app, then call /2fa/verify/.",
            }
        )


class TwoFactorVerifyView(APIView):
    """
    POST /api/v1/auth/2fa/verify/

    Verify the TOTP code from the authenticator app and permanently
    activate 2FA for the requesting Admin.

    Request body
    ------------
    { "totp_code": "123456" }
    """

    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request) -> Response:
        user: User = request.user  # type: ignore[assignment]
        totp_code: str = request.data.get("totp_code", "")
        pending_secret: str = request.session.get("pending_2fa_secret", "")

        if not pending_secret:
            return Response(
                {
                    "success": False,
                    "error": {
                        "code": "INVALID_STATE",
                        "message": "No pending 2FA setup found. Call /2fa/setup/ first.",
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        totp = pyotp.TOTP(pending_secret)
        if not totp.verify(totp_code, valid_window=1):
            return Response(
                {
                    "success": False,
                    "error": {"code": "TOTP_INVALID", "message": "Invalid TOTP code. Please try again."},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Activate 2FA permanently
        user.two_factor_secret = pending_secret
        user.save(update_fields=["two_factor_secret"])
        del request.session["pending_2fa_secret"]

        AuditLog.objects.log_action(
            action_type=AuditActionType.PASSWORD_CHANGED,
            user=user,
            details={"event": "2FA activated"},
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        logger.info("2FA activated for user: %s", user.username)
        return Response(
            {"success": True, "message": "Two-factor authentication has been activated."}
        )
