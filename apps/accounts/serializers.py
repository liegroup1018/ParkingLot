"""
Serializers for the accounts app.

Track 1 / Task 1.6 - JWT Authentication.

Includes:
  - ParkingTokenObtainPairSerializer : Adds role + 2FA status to JWT claims
  - UserCreateSerializer             : Admin-only staff creation
  - UserReadSerializer               : Safe read-only user representation
  - AuditLogSerializer               : Read-only audit log entries
"""

import pyotp
from django.contrib.auth import user_logged_in, user_login_failed
from django.contrib.auth.models import update_last_login
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenObtainSerializer,
)
from rest_framework_simplejwt.settings import api_settings

from apps.accounts.models import AuditLog, User


# ---------------------------------------------------------------------------
# JWT - Custom token claims (Task 1.6)
# ---------------------------------------------------------------------------
class ParkingTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the default JWT payload with parking-lot-specific claims.

    Added claims
    ------------
    role        : "ADMIN" | "ATTENDANT"
    username    : str
    has_2fa     : bool
    """

    @classmethod
    def get_token(cls, user: User):
        token = super().get_token(user)
        token["role"] = user.role
        token["username"] = user.username
        token["has_2fa"] = user.has_2fa_configured
        return token

    def validate(self, attrs: dict) -> dict:
        # Authenticate first; invalid username/password already emits
        # Django's `user_login_failed` signal inside authenticate().
        # 该函数会自动调用 authenticate() 验证用户名和密码，如果出现错误会发射 failed 信号
        TokenObtainSerializer.validate(self, attrs)
        user: User = self.user
        request = self.context.get("request")

        # For Admin accounts that have a TOTP secret, require a valid OTP code.
        if user.is_admin and user.has_2fa_configured:
            totp_code = attrs.get("totp_code", "")
            totp = pyotp.TOTP(user.two_factor_secret)
            if not totp.verify(totp_code, valid_window=1):
                user_login_failed.send(
                    sender=__name__,
                    credentials={self.username_field: attrs.get(self.username_field, "")},
                    request=request,
                )
                raise serializers.ValidationError(
                    {"totp_code": "Invalid or expired TOTP code. Please try again."}
                )

        # Issue JWT pair only after all auth factors pass.
        refresh = self.get_token(user)
        data = {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

        if api_settings.UPDATE_LAST_LOGIN:
            update_last_login(None, user)

        # JWT login doesn't call `django.contrib.auth.login()`, so emit this
        # explicitly to keep signal-driven audit logging consistent.
        user_logged_in.send(sender=user.__class__, request=request, user=user)

        data["user"] = {
            "id": user.pk,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "role_display": user.get_role_display(),
            "has_2fa": user.has_2fa_configured,
        }
        return data


# ---------------------------------------------------------------------------
# User serializers
# ---------------------------------------------------------------------------
class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new staff accounts (Admin-only endpoint).

    Enforces Django's built-in password validators and hashes the password
    before saving.
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "password",
            "password_confirm",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data: dict) -> User:
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserReadSerializer(serializers.ModelSerializer):
    """
    Safe, read-only representation of a User.
    Never exposes password hash or two_factor_secret.
    """

    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "role_display",
            "is_active",
            "has_2fa_configured",
            "date_joined",
            "last_login",
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# AuditLog serializer
# ---------------------------------------------------------------------------
class AuditLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for audit log entries (Admin dashboard)."""

    username = serializers.CharField(
        source="user.username", read_only=True, default="system"
    )
    action_type_display = serializers.CharField(
        source="get_action_type_display", read_only=True
    )

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "username",
            "action_type",
            "action_type_display",
            "details",
            "ip_address",
            "timestamp",
        ]
        read_only_fields = fields
