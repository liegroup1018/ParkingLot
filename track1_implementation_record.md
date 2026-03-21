# Track 1 — Foundation & Identity: Implementation Record

> **Status:** ✅ Complete  
> **Track:** `foundation-setup`  
> **Date:** 2026-03-12

---

## What Was Built

Track 1 established the entire project skeleton and the Identity & Access Management (IAM) layer. Every item in [ROADMAP.md](file:///e:/python%20project/ParkingLot/ROADMAP.md) is now checked off.

---

## File Tree

```
ParkingLot/
├── manage.py                           # Django entry point
├── requirements.txt                    # Pinned dependencies
├── .env                                # Local config (gitignore this!)
├── .env.example                        # Safe template to commit
│
├── config/                             # Project-level settings package
│   ├── __init__.py
│   ├── settings.py                     # Task 1.2 — MySQL + JWT + DRF config
│   ├── urls.py                         # Root URLconf
│   └── wsgi.py                         # Production WSGI entry point
│
└── apps/
    ├── __init__.py
    ├── core/
    │   ├── __init__.py
    │   └── exceptions.py               # Global DRF exception handler
    │
    └── accounts/                       # IAM app (Task 1.1)
        ├── __init__.py
        ├── apps.py                     # AppConfig + signal registration
        ├── models.py                   # Task 1.3 & 1.5 — User + AuditLog
        ├── managers.py                 # AuditLogManager (append-only)
        ├── signals.py                  # Auto-logs login/create events
        ├── serializers.py              # Task 1.6 — JWT + User serializers
        ├── permissions.py              # RBAC permission classes
        ├── views.py                    # Auth endpoints + 2FA flow
        ├── urls.py                     # URL routes
        ├── admin.py                    # Django Admin interface
        ├── tests.py                    # Full test suite
        └── migrations/
            ├── __init__.py
            └── 0001_initial.py         # Task 1.4 — initial migration
```

---

## Task-by-Task Record

### Task 1.1 — Django Project & App Structure ✅
- Created [manage.py](file:///e:/python%20project/ParkingLot/manage.py), [config/](file:///e:/python%20project/ParkingLot/apps/accounts/models.py#102-106) package, and `apps/` namespace
- Two apps: `apps.core` (shared utilities) and `apps.accounts` (IAM)
- Clean separation of `DJANGO_APPS`, `THIRD_PARTY_APPS`, `LOCAL_APPS` in settings

### Task 1.2 — MySQL Database Configuration ✅
- [config/settings.py](file:///e:/python%20project/ParkingLot/config/settings.py) reads all DB credentials from [.env](file:///e:/python%20project/ParkingLot/.env) via `django-environ`
- `STRICT_TRANS_TABLES` mode enforced to catch data integrity errors early
- `utf8mb4` charset configured (supports emoji and full Unicode)
- `CONN_MAX_AGE=60` for persistent connection reuse

### Task 1.3 — Custom User Model ✅
**File:** [apps/accounts/models.py](file:///e:/python%20project/ParkingLot/apps/accounts/models.py) → class [User(AbstractUser)](file:///e:/python%20project/ParkingLot/apps/accounts/models.py#55-109)

| Field | Type | Notes |
|---|---|---|
| `role` | `CharField(choices=UserRole)` | `db_index=True`; ADMIN \| ATTENDANT |
| `two_factor_secret` | `CharField(64)` | Empty = 2FA not set up yet |

- Composite index `idx_users_role_active` on [(role, is_active)](file:///e:/python%20project/ParkingLot/apps/accounts/views.py#206-224) for fast RBAC checks
- Business properties: [is_admin](file:///e:/python%20project/ParkingLot/apps/accounts/models.py#92-96), [is_attendant](file:///e:/python%20project/ParkingLot/apps/accounts/models.py#97-101), [has_2fa_configured](file:///e:/python%20project/ParkingLot/apps/accounts/models.py#102-106)
- Extending `AbstractUser` preserves Django Admin, group/permission machinery

### Task 1.4 — Migrations ✅
**File:** [apps/accounts/migrations/0001_initial.py](file:///e:/python%20project/ParkingLot/apps/accounts/migrations/0001_initial.py)

- Hand-written to be fully transparent and reviewable
- Creates `accounts_users` and `accounts_audit_logs` tables
- All composite indexes (`idx_users_role_active`, `idx_audit_user_timestamp`, `idx_audit_type_timestamp`) applied in the migration

> **To apply:** `python manage.py migrate`

### Task 1.5 — AuditLogs Model ✅
**File:** [apps/accounts/models.py](file:///e:/python%20project/ParkingLot/apps/accounts/models.py) → class [AuditLog](file:///e:/python%20project/ParkingLot/apps/accounts/models.py#114-187)

| Field | Type | `db_index` | Rationale |
|---|---|---|---|
| [user](file:///e:/python%20project/ParkingLot/apps/accounts/signals.py#16-34) | FK → User | ✅ (FK default) | JOIN for per-user log pages |
| `action_type` | `CharField(choices)` | ✅ explicit | Filter by event type |
| `details` | `JSONField` | ❌ | Payload, not queried |
| `ip_address` | `GenericIPAddressField` | ❌ | Display only |
| `timestamp` | `DateTimeField(auto_now_add)` | ✅ explicit | ORDER BY, date ranges |

**`on_delete` rationale:**
- [user](file:///e:/python%20project/ParkingLot/apps/accounts/signals.py#16-34) → `SET_NULL`: Audit records must survive even if the staff member's account is deleted. An orphaned log with `user=NULL` is infinitely preferable to losing the audit trail entirely.

**Composite indexes:**
- `idx_audit_user_timestamp` [(user_id, -timestamp)](file:///e:/python%20project/ParkingLot/apps/accounts/views.py#206-224) — "show me all actions by Admin A this week"
- `idx_audit_type_timestamp` [(action_type, -timestamp)](file:///e:/python%20project/ParkingLot/apps/accounts/views.py#206-224) — "show me all MANUAL_GATE_OPEN today"

**`AuditLogManager.log_action()`** — Convenience method with explicit keyword-only args to prevent argument positional mistakes.

**Signals** ([apps/accounts/signals.py](file:///e:/python%20project/ParkingLot/apps/accounts/signals.py)) auto-log:
- `USER_CREATED` on `post_save`
- `LOGIN_SUCCESS` / `LOGIN_FAILED` via Django's built-in auth signals

### Task 1.6 — JWT Authentication ✅
**Files:** [serializers.py](file:///e:/python%20project/ParkingLot/apps/accounts/serializers.py), [views.py](file:///e:/python%20project/ParkingLot/apps/accounts/views.py), [urls.py](file:///e:/python%20project/ParkingLot/config/urls.py)

**Token customisation ([ParkingTokenObtainPairSerializer](file:///e:/python%20project/ParkingLot/apps/accounts/serializers.py#23-72)):**
- Embeds `role`, `username`, [has_2fa](file:///e:/python%20project/ParkingLot/apps/accounts/models.py#102-106) into the JWT payload
- For Admin accounts with `two_factor_secret` set, validates `totp_code` field during login before issuing tokens

**Endpoints:**

| Method | Path | Permission | Description |
|---|---|---|---|
| POST | `/api/v1/auth/login/` | Public | Issue JWT pair |
| POST | `/api/v1/auth/refresh/` | Public | Rotate access token |
| POST | `/api/v1/auth/logout/` | Any auth | Blacklist refresh token |
| GET  | `/api/v1/auth/users/` | Admin | List staff accounts |
| POST | `/api/v1/auth/users/` | Admin | Create staff account |
| GET  | `/api/v1/auth/users/me/` | Any auth | Own profile |
| GET  | `/api/v1/auth/audit-logs/` | Admin | Paginated audit log |
| POST | `/api/v1/auth/2fa/setup/` | Admin | Generate TOTP provisioning URI |
| POST | `/api/v1/auth/2fa/verify/` | Admin | Activate 2FA on account |

**RBAC permission classes** ([permissions.py](file:///e:/python%20project/ParkingLot/apps/accounts/permissions.py)):
- [IsAdminRole](file:///e:/python%20project/ParkingLot/apps/accounts/permissions.py#18-34) — Admin-only endpoints
- [IsAttendantRole](file:///e:/python%20project/ParkingLot/apps/accounts/permissions.py#36-51) — Attendant-only endpoints
- [IsAdminOrAttendant](file:///e:/python%20project/ParkingLot/apps/accounts/permissions.py#53-64) — Any authenticated staff

**JWT settings (from [.env](file:///e:/python%20project/ParkingLot/.env)):**
- Access token: 60 minutes
- Refresh token: 7 days, rotated + blacklisted on use (via `rest_framework_simplejwt.token_blacklist`)

---

## Key Design Decisions

### 1. `AbstractUser` vs `AbstractBaseUser`
Chose `AbstractUser` to keep Django's full permissions/groups framework. Only two new fields were needed — extending the existing model costs nothing.

### 2. `db_index` strategy
Added explicit indexes everywhere a field appears in a `WHERE`, `ORDER BY`, or `JOIN`. Used **composite** indexes (`idx_users_role_active`, etc.) where multi-column queries are expected, so MySQL can satisfy queries from the index alone without touching the data pages.

### 3. `SET_NULL` on AuditLog.user
Audit records are append-only compliance data. Cascading deletion of logs when a user is removed would violate PRD §4.2's audit requirement. `SET_NULL` is the only safe choice.

### 4. Token blacklisting
`ROTATE_REFRESH_TOKENS=True` + `BLACKLIST_AFTER_ROTATION=True` ensures that a stolen refresh token can only be used once; the next rotation invalidates it and the server detects the anomaly.

### 5. Exception handler
[apps/core/exceptions.py](file:///e:/python%20project/ParkingLot/apps/core/exceptions.py) wraps all DRF exceptions in a consistent `{ "success": false, "error": { "code": "...", "message": "..." } }` envelope so frontend clients have a single contract to program against.

---

## How to Run

```bash
# 1. Create virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and edit .env
copy .env.example .env
# → Update DB_PASSWORD with your MySQL root password

# 4. Create the MySQL database
mysql -u root -p -e "CREATE DATABASE parking_lot_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 5. Run migrations (Task 1.4)
python manage.py migrate

# 6. Create a superuser
python manage.py createsuperuser

# 7. Run the dev server
python manage.py runserver

# 8. Run tests
python manage.py test apps.accounts -v 2
```

---

## Next: Track 2 — Core Inventory (`core-inventory`)

The next track will add:
- `ParkingSpots` model (spot_id, size_type, status)
- `LotOccupancy` model with `version` for Optimistic Concurrency Control
- Admin API `POST /api/v1/spots` to seed the database
- Management command to initialise `LotOccupancy` from spot data
