"""
Admin UI Views — Track 7 (Auth Unification)

Both views are now pure template renderers.  All authentication and
authorization is handled client-side (JWT Bearer token stored in
sessionStorage) and enforced server-side by DRF's IsAdminRole permission
class on the API endpoints.

Session-based AdminLoginView has been removed.  The login page now
calls POST /api/v1/auth/login/ directly via fetch(), exactly the same
pattern as the Attendant UI.

URL layout (wired via config/urls.py → /admin-dashboard/):
  GET  /admin-dashboard/login/  → AdminLoginView  (renders login.html)
  GET  /admin-dashboard/        → AdminDashboardView (renders dashboard.html)
"""
from django.views.generic import TemplateView


class AdminLoginView(TemplateView):
    """
    Render the admin login page.

    No server-side authentication is performed here.  The template's
    JavaScript calls POST /api/v1/auth/login/ (which validates
    credentials, 2FA TOTP, and the ADMIN role), stores the returned
    JWT pair in sessionStorage, then redirects to the dashboard.
    """
    template_name = "admin_ui/login.html"


class AdminDashboardView(TemplateView):
    """
    Render the admin dashboard shell.

    No session guard — the template's JavaScript reads the JWT access
    token from sessionStorage on page load.  If no valid token is found,
    it immediately redirects to /admin-dashboard/login/.

    All data is fetched from DRF API endpoints using:
      Authorization: Bearer <access_token>
    The DRF IsAdminRole permission class enforces the role check.
    """
    template_name = "admin_ui/dashboard.html"
