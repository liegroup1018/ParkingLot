"""
URL routes for the accounts app.

All paths are prefixed with /api/v1/auth/ from the root URLconf.
"""
from django.urls import path

from apps.accounts.views import (
    AuditLogListView,
    CurrentUserView,
    LoginView,
    LogoutView,
    RefreshTokenView,
    TwoFactorSetupView,
    TwoFactorVerifyView,
    UserListCreateView,
)

app_name = "accounts"

urlpatterns = [
    # JWT Auth
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),

    # User management
    path("users/", UserListCreateView.as_view(), name="user-list-create"),
    path("users/me/", CurrentUserView.as_view(), name="current-user"),

    # Audit logs (Admin dashboard)
    path("audit-logs/", AuditLogListView.as_view(), name="audit-log-list"),

    # 2FA
    path("2fa/setup/", TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("2fa/verify/", TwoFactorVerifyView.as_view(), name="2fa-verify"),
]
