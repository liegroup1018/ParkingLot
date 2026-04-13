# Track 6 Implementation Record: Admin Dashboard & Analytics

This document summarizes the changes made to `apps/payments`, `apps/inventory`, and `apps/gates` to fulfill the roadmap requirements for "Track 6: Admin Dashboard & Analytics".

## Changes Made

### 1. Lot Occupancy Monitoring
- Mapped `GET /api/v1/lot/occupancy/` explicitly in `config/urls.py` bridging to `LotOccupancyView` (previously exported as `spots/occupancy`).

### 2. Dynamic Pricing Rule Management
- Created `PricingRuleReadSerializer` and `PricingRuleUpdateSerializer` in `apps/payments/serializers.py` to handle read and update data transformations.
- Added `PricingRuleUpdateView` (`RetrieveUpdateAPIView`) in `apps/payments/views.py`, protected by the `IsAdminRole` permission for write actions and `IsAuthenticated` for reads.
- Mapped `PUT /api/v1/pricing-rules/{id}` in `apps/payments/urls.py` to allow admins to re-configure parking lot prices dynamically without deploying new code.

### 3. Revenue Analytics Reporting
- Created `RevenueReportView` (`APIView`) in `apps/payments/views.py` utilizing Django ORM aggregation (`Sum` and `Count`) scaling over `TruncDate`.
- The endpoint supports time window filtering (`start_date`, `end_date`) to slice revenue trends.
- Mapped `GET /api/v1/reports/revenue` in `apps/payments/urls.py` (protected uniformly by `IsAdminRole`).

### 4. Abandoned Vehicles Scanning
- Created a custom Django core management command `scan_abandoned` inside `apps/gates/management/commands/scan_abandoned.py`.
- Evaluates `Ticket` records leveraging the index on `(status, entry_time)` to quickly locate active tickets exceeding the 7-day stay limit.
- Serves as a standalone backend job that can be invoked via system Cron or Celery using `python manage.py scan_abandoned`.

### 5. Admin Dashboard Session-Based Login
- Added `LOGIN_URL = "/admin-dashboard/login/"` to `config/settings.py` so that `LoginRequiredMixin` dynamically redirects unauthenticated traffic trying to access the dashboard.
- Created `AdminLoginView` inside `apps/admin_ui/views.py` utilizing built-in auth utilities and pyotp.
- Recreated the authentication flow natively with HTML instead of JWT payload exclusively for the dashboard, retaining strict enforcement on the `totp_code` and checking for the ADMIN role.
- Mapped `GET/POST /admin-dashboard/login/` via `apps/admin_ui/urls.py` corresponding to the custom login template in `apps/admin_ui/templates/admin_ui/login.html`.

## Validation Results
- Syntactic integration and URL configuration have been statically verified through `python manage.py check`, resulting in 0 system issues.
