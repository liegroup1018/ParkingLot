"""
Custom DRF permission classes for RBAC.

PRD §4.2: Strict segregation of duties.
  - Attendants only access payment/operational endpoints.
  - Admins have full access but must complete 2FA.

Usage
-----
    class MyView(APIView):
        permission_classes = [IsAuthenticated, IsAdminUser]
"""
from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole


class IsAdminRole(BasePermission):
    """
    Grants access only to users with the ADMIN role.

    Used on Admin-only endpoints such as pricing rule updates,
    spot management, and revenue reports.
    """

    message = "Access restricted to Management Admins only."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.ADMIN
        )


class IsAttendantRole(BasePermission):
    """
    Grants access only to ATTENDANT users.

    Used on operational endpoints (ticket scanning, payments).
    """

    message = "Access restricted to Parking Attendants only."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.ATTENDANT
        )


class IsAdminOrAttendant(BasePermission):
    """Grants access to either role — blocks unauthenticated requests."""

    message = "Authentication required."

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in (UserRole.ADMIN, UserRole.ATTENDANT)
        )
