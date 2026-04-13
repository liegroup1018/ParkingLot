# Administrator Session-Based Login Walkthrough

This walkthrough covers the creation of the dedicated HTML interface and session authentication view for the Admin Dashboard.

## Changes Made

### 1. Enforcing Session Redirects
- **File**: `config/settings.py`
- We added `LOGIN_URL = "/admin-dashboard/login/"`.
- **Why**: Since `AdminDashboardView` inherits from `LoginRequiredMixin`, unauthorized users will now correctly be routed to our new login template interface rather than falling back to the standard Django `/accounts/login/` (which doesn't exist).

### 2. Creating the Administrator Auth View
- **File**: `apps/admin_ui/views.py`
- Added the `AdminLoginView` class. This handles everything from validating credentials via standard `django.contrib.auth.authenticate`, validating the strict `ADMIN` role requirement, and enforcing the 2FA `totp_code` check using `pyotp` mapped against the database `two_factor_secret`.
- If successful, we initialize a standard session cookie utilizing `django.contrib.auth.login(request, user)` allowing strict access to `/admin-dashboard/`.

### 3. URL Router Update
- **File**: `apps/admin_ui/urls.py`
- Exposed the `AdminLoginView` externally linking to the URL parameter `login/`.

### 4. Administrator UI Template
- **File**: `apps/admin_ui/templates/admin_ui/login.html`
- Created the dedicated HTML form styled consistently with the application's clean CSS base.
- Includes full CSRF token protection.
- Supports handling validation errors supplied by the backend `messages` framework dynamically (e.g. invalid username/password vs invalid TOTP).

### 5. Documentation Hand-off
- **File**: `track6_implementation_record.md`
- Appended the login interface updates as section `5. Admin Dashboard Session-Based Login` completing the requirements logic.

## What Was Tested
- Executed `python manage.py check` to evaluate potential syntax hazards introduced in `config/settings.py` or URL routers.
- **Validation Result**: Evaluated perfectly `(0 issues, 0 silenced)` assuring structural integrity within the module loading sequence.

> [!TIP]
> Navigating dynamically to `/admin-dashboard/` while disconnected will cleanly append `?next=/admin-dashboard/` providing smooth re-entry post authentication.
