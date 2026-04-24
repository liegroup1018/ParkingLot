# Apps Python File Review

## Scope and context used
- Reviewed source code under `apps/` for: `accounts`, `admin_ui`, `attendant_ui`, `core`, `gates`, `inventory`, `payments`.
- Used context from `prd.md`, `system_design.md`, and implementation records `track1_implementation_record.md` to `track8_implementation_record.md`.
- Ignored `apps/__pycache__/` because it is bytecode cache, not an application module.

## `accounts` app (IAM, RBAC, JWT, 2FA, audit)

### `views.py` functions and operations
- `LoginView` (`TokenObtainPairView`): authenticates username/password, enforces TOTP for 2FA-enabled admins via serializer, returns JWT access/refresh + user payload.
- `RefreshTokenView` (`TokenRefreshView`): exchanges refresh token for a new access token.
- `LogoutView.post()`: requires auth, validates refresh token presence, blacklists it, emits `user_logged_out` signal, returns success/error envelope.
- `UserListCreateView`:
  - `GET`: admin-only paginated user listing with selected columns.
  - `POST`: admin-only staff creation via `UserCreateSerializer`; audit creation handled by signals.
- `CurrentUserView.get_object()`: returns authenticated user profile (`/users/me/`).
- `AuditLogListView.get_queryset()`: admin-only audit feed, newest-first, optional filter by `action_type` and `user_id`.
- `TwoFactorSetupView.post()`: admin-only, creates temporary TOTP secret + provisioning URI, stores secret in session as pending setup.
- `TwoFactorVerifyView.post()`: admin-only, verifies TOTP against pending secret, persists `two_factor_secret`, writes audit event, clears pending session key.

### Purpose of every `.py` file
- `apps/accounts/__init__.py`: package marker for Django app namespace.
- `apps/accounts/apps.py`: app config (`AccountsConfig`) and signal registration in `ready()`.
- `apps/accounts/models.py`: custom `User`, `AuditLog`, RBAC/action enums, indexes/constraints.
- `apps/accounts/managers.py`: append-only `AuditLogManager.log_action()` helper.
- `apps/accounts/permissions.py`: DRF role permissions (`IsAdminRole`, `IsAttendantRole`, `IsAdminOrAttendant`).
- `apps/accounts/serializers.py`: JWT serializer customization, user create/read serializers, audit serializer.
- `apps/accounts/signals.py`: audit logging receivers for user creation, login success/failure, logout.
- `apps/accounts/views.py`: auth/user/2FA/audit API endpoints.
- `apps/accounts/urls.py`: route map for `/api/v1/auth/*` endpoints.
- `apps/accounts/admin.py`: hardened Django admin setup for users and read-only audit logs.
- `apps/accounts/tests.py`: unit/API tests for user model, audit behavior, login/logout, user management.
- `apps/accounts/migrations/__init__.py`: migration package marker.
- `apps/accounts/migrations/0001_initial.py`: creates `accounts_users` and `accounts_audit_logs` schema with indexes.

## `admin_ui` app (admin HTML shell)

### `views.py` functions and operations
- `AdminLoginView` (`TemplateView`): renders admin login page; page JS calls JWT login API.
- `AdminDashboardView` (`TemplateView`): renders dashboard shell; page JS enforces token presence and calls protected admin APIs with Bearer token.

### Purpose of every `.py` file
- `apps/admin_ui/__init__.py`: package marker.
- `apps/admin_ui/apps.py`: Django app registration (`AdminUiConfig`).
- `apps/admin_ui/views.py`: template-render-only views after session-to-JWT unification.
- `apps/admin_ui/urls.py`: routes for `/admin-dashboard/login/` and `/admin-dashboard/`.

## `attendant_ui` app (attendant HTML frontend)

### `views.py` functions and operations
- `AttendantLoginView.get()`: renders login page.
- `AttendantDashboardView.get()`: renders occupancy/ticket dashboard shell and sets `active_page` context.
- `AttendantScanTicketView.get()`: renders scan-and-fee page and sets `active_page`.
- `AttendantCheckoutView.get()`: renders payment checkout page and sets `active_page`.
- All business operations are client-side via API calls (`/tickets/scan`, `/payments`, `/spots/occupancy`, `/gates/tickets`).

### Purpose of every `.py` file
- `apps/attendant_ui/__init__.py`: package marker.
- `apps/attendant_ui/views.py`: template-serving views for attendant pages.
- `apps/attendant_ui/urls.py`: route map under `/attendant/`.

## `core` app (shared API behavior)

### `views.py`
- No `views.py` file in this app.

### Purpose of every `.py` file
- `apps/core/__init__.py`: package marker.
- `apps/core/exceptions.py`: global DRF exception handler; normalizes all API errors to consistent `{ success: false, error: { code, message } }` envelope.

## `gates` app (entry flow, overrides, ticket APIs)

### `views.py` functions and operations
- `_get_ip(request)`: resolves client IP (`X-Forwarded-For` fallback to `REMOTE_ADDR`).
- `GateEntryView.post()`: validates entry request, invokes OCC-aware `EntryService.process_entry()`, returns 201 ticket or 409 `LOT_FULL`/`OCC_CONFLICT`.
- `GateOverrideView.post(gate_id)`: admin-only manual gate open without ticket issuance, validates payload, writes audit through `OverrideService`.
- `TicketListView.get()`: authenticated list endpoint with optional `status` and `vehicle_type` filters.
- `TicketDetailView.get(ticket_code)`: authenticated lookup by printed ticket code; returns ticket or 404.

### Purpose of every `.py` file
- `apps/gates/__init__.py`: package marker.
- `apps/gates/apps.py`: app registration (`GatesConfig`).
- `apps/gates/models.py`: `Ticket` domain model, status enum, ticket-code generator, constraints/indexes.
- `apps/gates/serializers.py`: request/response serializers for entry, override, and ticket reads.
- `apps/gates/services.py`: service-layer orchestration for OCC entry retries and manual override auditing.
- `apps/gates/views.py`: gate/ticket API endpoints.
- `apps/gates/urls.py`: route map for entry, override, ticket list/detail.
- `apps/gates/admin.py`: Django admin for tickets, includes bulk void action.
- `apps/gates/tests.py`: model/service/API tests for entry, overrides, and ticket endpoints.
- `apps/gates/management/__init__.py`: management package marker.
- `apps/gates/management/commands/__init__.py`: management commands package marker.
- `apps/gates/management/commands/scan_abandoned.py`: management command that finds and reports open tickets older than 7 days.
- `apps/gates/migrations/__init__.py`: migration package marker.
- `apps/gates/migrations/0001_initial.py`: creates `gates_tickets` schema with checks and indexes.
- `apps/gates/migrations/0002_alter_ticket_assigned_size_alter_ticket_entry_time.py`: alters help-text/field metadata for `Ticket` fields.

## `inventory` app (spot inventory + OCC counters)

### `views.py` functions and operations
- `ParkingSpotListCreateView`:
  - `GET`: authenticated list with optional `size_type`/`status` filters and pagination.
  - `POST`: admin-only create spot; returns created record in success envelope.
- `ParkingSpotDetailView`:
  - `GET`: authenticated detail view.
  - `PATCH`: admin-only partial updates (status-only serializer).
  - `DELETE`: admin-only deletion with success message.
- `BulkSpotSeedView.post()`: admin-only idempotent bulk spot creation by counts (`COMPACT/REGULAR/OVERSIZED`).
- `SpotSummaryView.get()`: authenticated aggregated counts by size and status using annotated query.
- `LotOccupancyView.get()`: authenticated snapshot of OCC table (`total/current/available/version`) for dashboards.

### Purpose of every `.py` file
- `apps/inventory/__init__.py`: package marker.
- `apps/inventory/apps.py`: app registration (`InventoryConfig`).
- `apps/inventory/models.py`: `ParkingSpot`, `LotOccupancy`, spot/vehicle/status enums, overflow priority, OCC helpers (`attempt_reserve`, `attempt_release`, `available_size_for_vehicle`).
- `apps/inventory/serializers.py`: spot CRUD serializers, bulk seed serializer, occupancy and summary serializers.
- `apps/inventory/views.py`: inventory CRUD/analytics endpoints.
- `apps/inventory/urls.py`: route map under `/api/v1/spots/`.
- `apps/inventory/admin.py`: admin UI for spot management and read-only occupancy table.
- `apps/inventory/tests.py`: tests for models, OCC behavior, APIs, and occupancy init command.
- `apps/inventory/management/__init__.py`: management package marker.
- `apps/inventory/management/commands/__init__.py`: management command package marker.
- `apps/inventory/management/commands/init_lot_occupancy.py`: command to initialize/resync `LotOccupancy` from active spot counts (optionally preserving live counters).
- `apps/inventory/migrations/__init__.py`: migration package marker.
- `apps/inventory/migrations/0001_initial.py`: creates `inventory_parking_spots` and `inventory_lot_occupancy` schema with checks/indexes.

## `payments` app (scan pricing, payment processing, pricing/admin analytics)

### `views.py` functions and operations
- `TicketScanView.post()`: validates ticket code, ensures ticket is OPEN, computes billable duration, resolves active pricing rule, applies hourly charge and per-day cap, returns amount owed breakdown.
- `PaymentProcessView.post()`: validates payload, re-computes owed amount to prevent underpayment, creates `Payment`, marks ticket `PAID` with exit time, attempts OCC release retry loop for assigned spot, returns payment success payload.
- `PricingRuleUpdateView`:
  - `GET`: authenticated pricing rule detail.
  - `PUT/PATCH`: admin-only update of rates/active flag.
  - `perform_update()`: writes audit log with old/new values and client IP.
- `RevenueReportView.get()`: admin-only daily aggregation of successful payments (`total_revenue`, `payment_count`) with optional date window.
- `PeakHoursReportView.get()`: admin-only grouping of ticket entries by hour (defaults to current date if query param absent).

### Purpose of every `.py` file
- `apps/payments/__init__.py`: package marker.
- `apps/payments/apps.py`: app registration (`PaymentsConfig`).
- `apps/payments/models.py`: pricing and payment domain models, method/status enums, constraints.
- `apps/payments/serializers.py`: input/output serializers for ticket scan, payment create, and pricing rule read/update.
- `apps/payments/views.py`: fee calculation, payment settlement, pricing admin, and reporting endpoints.
- `apps/payments/urls.py`: route map for `/tickets/scan/`, `/payments/`, `/pricing-rules/<id>/`, and reports.
- `apps/payments/admin.py`: Django admin registration for pricing rules and payment records.
- `apps/payments/tests.py`: currently a placeholder/no implemented tests.
- `apps/payments/migrations/__init__.py`: migration package marker.
- `apps/payments/migrations/0001_initial.py`: creates `payments_pricing_rules` and `payments_transactions` schema.
- `apps/payments/migrations/0002_seed_pricing_rules.py`: data migration that seeds default pricing matrix and provides reverse deletion.

## Namespace-level Python file
- `apps/__init__.py`: root package marker for the project’s app namespace.
