"""
Serializers for the accounts app.

Track 1 / Task 1.6 — JWT Authentication.

Includes:
  - ParkingTokenObtainPairSerializer : Adds role + 2FA status to JWT claims
  - UserCreateSerializer             : Admin-only staff creation
  - UserReadSerializer               : Safe read-only user representation
  - AuditLogSerializer               : Read-only audit log entries
"""
import pyotp
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.accounts.models import AuditLog, User, UserRole


# ---------------------------------------------------------------------------
# JWT — Custom token claims (Task 1.6)
# ---------------------------------------------------------------------------
class ParkingTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the default JWT payload with parking-lot-specific claims.

    Added claims
    ------------
    role        : "ADMIN" | "ATTENDANT"
    is_2fa_ok   : bool — True if the user has successfully verified TOTP
    username    : str  — human-readable claim for frontend display
    """
    # 生成新的 Token
    @classmethod
    def get_token(cls, user: User):
        token = super().get_token(user)
        # Embed role so the frontend / API gateway can do basic RBAC without
        # a separate /me endpoint on every request.
        token["role"] = user.role
        token["username"] = user.username
        # Admins require 2FA; surface the *configured* state in the token.
        # The view layer decides whether to issue a full-access token or a
        # limited "2FA pending" token.
        token["has_2fa"] = user.has_2fa_configured
        return token # 返回的 token 包含哪些内容

    """
    普通用户：账号密码正确 → 直接发 Token (不需要执行 validate())
    管理员：账号密码 + 验证码都正确（validate()） → 才发 Token
    """
    def validate(self, attrs: dict) -> dict:
        data = super().validate(attrs) # 验证用户名和密码
        user: User = self.user

        # For Admin accounts that have a TOTP secret, require the OTP code.
        # The TOTP field is optional during login — if the admin hasn't
        # configured 2FA yet they can still log in (first-time setup flow).
        if user.is_admin and user.has_2fa_configured:
            totp_code = attrs.get("totp_code", "")
            totp = pyotp.TOTP(user.two_factor_secret)
            if not totp.verify(totp_code, valid_window=1):
                raise serializers.ValidationError(
                    {"totp_code": "Invalid or expired TOTP code. Please try again."}
                )

        # Append user metadata to the response body alongside the tokens.
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
    before saving — never stores plaintext.
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
        read_only_fields = ["id"] # 忽略 id 的值

    def validate(self, attrs: dict) -> dict:
        if attrs["password"] != attrs.pop("password_confirm"):
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )
        return attrs

    def create(self, validated_data: dict) -> User:
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)   # hashes via Django's PBKDF2
        user.save()
        return user


class UserReadSerializer(serializers.ModelSerializer):
    """
    Safe, read-only representation of a User.
    Never exposes password_hash or two_factor_secret.
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
