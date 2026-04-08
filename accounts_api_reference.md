# Accounts App — API Input / Output Reference

> Source: [`apps/accounts/views.py`](file:///e:/python%20project/ParkingLot/apps/accounts/views.py)
> All endpoints are prefixed with `/api/v1/auth/`

---

## Table of Contents

| # | View Class | Method | Endpoint | Auth |
|---|------------|--------|----------|------|
| 1 | [`LoginView`](#1-loginview) | `POST` | `/api/v1/auth/login/` | None |
| 2 | [`RefreshTokenView`](#2-refreshtokenview) | `POST` | `/api/v1/auth/refresh/` | None |
| 3 | [`LogoutView`](#3-logoutview) | `POST` | `/api/v1/auth/logout/` | JWT (Any role) |
| 4 | [`UserListCreateView`](#4-userlistcreateview) | `GET` / `POST` | `/api/v1/auth/users/` | JWT (Admin) |
| 5 | [`CurrentUserView`](#5-currentuserview) | `GET` | `/api/v1/auth/users/me/` | JWT (Any role) |
| 6 | [`AuditLogListView`](#6-auditloglistview) | `GET` | `/api/v1/auth/audit-logs/` | JWT (Admin) |
| 7 | [`TwoFactorSetupView`](#7-twofactorsetupview) | `POST` | `/api/v1/auth/2fa/setup/` | JWT (Admin) |
| 8 | [`TwoFactorVerifyView`](#8-twofactorverifyview) | `POST` | `/api/v1/auth/2fa/verify/` | JWT (Admin) |

---

## 1. LoginView

**Endpoint:** `POST /api/v1/auth/login/`
**Permission:** `AllowAny`
**View Class:** `TokenObtainPairView` (simplejwt) with custom serializer `ParkingTokenObtainPairSerializer`

### Request Body (JSON)

```json
{
    "username": "admin1",
    "password": "s3cr3t!",
    "totp_code": "123456"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | `string` | ✅ Yes | The user's login name. |
| `password` | `string` | ✅ Yes | The user's password (plaintext, validated server-side). |
| `totp_code` | `string` | ⚠️ Conditional | **Required only** for Admin accounts that have 2FA activated. Six-digit TOTP from an authenticator app. |

### Response — `200 OK` (Success)

```json
{
    "access": "eyJhbGciOiJIUzI1NiIs...",
    "refresh": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
        "id": 1,
        "username": "admin1",
        "email": "admin1@example.com",
        "role": "ADMIN",
        "role_display": "Management Admin",
        "has_2fa": true
    }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `access` | `string` | Short-lived JWT access token. Embed custom claims: `role`, `username`, `has_2fa`. |
| `refresh` | `string` | Long-lived JWT refresh token. Used to obtain new access tokens. |
| `user.id` | `integer` | Primary key of the authenticated user. |
| `user.username` | `string` | Login username. |
| `user.email` | `string` | Email address. |
| `user.role` | `string` | `"ADMIN"` or `"ATTENDANT"`. |
| `user.role_display` | `string` | Human-readable role label (e.g., `"Management Admin"`). |
| `user.has_2fa` | `boolean` | Whether the user has a TOTP secret configured. |

### Response — `401 Unauthorized` (Bad credentials)

```json
{
    "detail": "No active account found with the given credentials"
}
```

### Response — `400 Bad Request` (Invalid TOTP for 2FA admin)

```json
{
    "totp_code": ["Invalid or expired TOTP code. Please try again."]
}
```

---

## 2. RefreshTokenView

**Endpoint:** `POST /api/v1/auth/refresh/`
**Permission:** `AllowAny`
**View Class:** `TokenRefreshView` (simplejwt, unmodified)

### Request Body (JSON)

```json
{
    "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh` | `string` | ✅ Yes | A valid, non-blacklisted refresh token. |

### Response — `200 OK` (Success)

```json
{
    "access": "eyJhbGciOiJIUzI1NiIs..."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `access` | `string` | A newly issued JWT access token. |

### Response — `401 Unauthorized` (Invalid/expired refresh token)

```json
{
    "detail": "Token is invalid or expired",
    "code": "token_not_valid"
}
```

---

## 3. LogoutView

**Endpoint:** `POST /api/v1/auth/logout/`
**Permission:** `IsAuthenticated`
**Description:** Blacklists the supplied refresh token, effectively ending the user's session.

### Request Body (JSON)

```json
{
    "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh` | `string` | ✅ Yes | The refresh token to blacklist (invalidate). |

### Response — `200 OK` (Success)

```json
{
    "success": true,
    "message": "Logged out successfully."
}
```

### Response — `400 Bad Request` (Missing refresh token)

```json
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "refresh token is required."
    }
}
```

### Response — `400 Bad Request` (Invalid/expired token)

```json
{
    "success": false,
    "error": {
        "code": "TOKEN_INVALID",
        "message": "Token is blacklisted"
    }
}
```

---

## 4. UserListCreateView

**Endpoint:** `/api/v1/auth/users/`
**Permission:** `IsAuthenticated`, `IsAdminRole`

### 4a. `GET` — List All Staff Users

#### Request

No request body. Authentication via `Authorization: Bearer <access_token>` header.

#### Response — `200 OK`

```json
[
    {
        "id": 1,
        "username": "admin1",
        "email": "admin1@example.com",
        "first_name": "Alice",
        "last_name": "Wang",
        "role": "ADMIN",
        "role_display": "Management Admin",
        "is_active": true,
        "has_2fa_configured": true,
        "date_joined": "2026-03-12T08:00:00Z",
        "last_login": "2026-04-06T10:30:00Z"
    },
    {
        "id": 2,
        "username": "attendant1",
        "email": "att1@example.com",
        "first_name": "Bob",
        "last_name": "Li",
        "role": "ATTENDANT",
        "role_display": "Parking Attendant",
        "is_active": true,
        "has_2fa_configured": false,
        "date_joined": "2026-03-15T09:00:00Z",
        "last_login": "2026-04-05T14:20:00Z"
    }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `integer` | User primary key. |
| `username` | `string` | Login username. |
| `email` | `string` | Email address. |
| `first_name` | `string` | First name. |
| `last_name` | `string` | Last name. |
| `role` | `string` | `"ADMIN"` or `"ATTENDANT"`. |
| `role_display` | `string` | Human-readable role label. |
| `is_active` | `boolean` | Whether the account is enabled. |
| `has_2fa_configured` | `boolean` | Whether a TOTP secret exists for this user. |
| `date_joined` | `string (ISO 8601)` | Account creation timestamp. |
| `last_login` | `string (ISO 8601) \| null` | Most recent login timestamp, or `null`. |

---

### 4b. `POST` — Create a New Staff Account

#### Request Body (JSON)

```json
{
    "username": "attendant2",
    "email": "att2@example.com",
    "first_name": "Charlie",
    "last_name": "Zhang",
    "role": "ATTENDANT",
    "password": "Str0ng!Pass#2026",
    "password_confirm": "Str0ng!Pass#2026"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | `string` | ✅ Yes | Unique login name for the new user. |
| `email` | `string` | ❌ No | Email address. |
| `first_name` | `string` | ❌ No | First name. |
| `last_name` | `string` | ❌ No | Last name. |
| `role` | `string` | ❌ No | `"ADMIN"` or `"ATTENDANT"`. Defaults to `"ATTENDANT"`. |
| `password` | `string` | ✅ Yes | Must satisfy Django's password validators. **Write-only; never returned.** |
| `password_confirm` | `string` | ✅ Yes | Must match `password`. **Write-only; never returned.** |

#### Response — `201 Created` (Success)

```json
{
    "id": 3,
    "username": "attendant2",
    "email": "att2@example.com",
    "first_name": "Charlie",
    "last_name": "Zhang",
    "role": "ATTENDANT"
}
```

> [!NOTE]
> `password` and `password_confirm` are write-only — they never appear in any response.

#### Response — `400 Bad Request` (Validation error)

```json
{
    "password_confirm": ["Passwords do not match."],
    "username": ["A user with that username already exists."]
}
```

---

## 5. CurrentUserView

**Endpoint:** `GET /api/v1/auth/users/me/`
**Permission:** `IsAuthenticated`
**Description:** Returns the profile of the currently authenticated user. Accessible by **all roles**.

### Request

No request body. Authentication via `Authorization: Bearer <access_token>` header.

### Response — `200 OK`

```json
{
    "id": 1,
    "username": "admin1",
    "email": "admin1@example.com",
    "first_name": "Alice",
    "last_name": "Wang",
    "role": "ADMIN",
    "role_display": "Management Admin",
    "is_active": true,
    "has_2fa_configured": true,
    "date_joined": "2026-03-12T08:00:00Z",
    "last_login": "2026-04-06T10:30:00Z"
}
```

Fields are identical to those in the [User List response](#4a-get--list-all-staff-users).

---

## 6. AuditLogListView

**Endpoint:** `GET /api/v1/auth/audit-logs/`
**Permission:** `IsAuthenticated`, `IsAdminRole`
**Description:** Returns paginated audit log entries, newest first. Supports optional query-string filters.

### Request

No request body. Authentication via `Authorization: Bearer <access_token>` header.

#### Optional Query Parameters

| Parameter | Type | Example | Description |
|-----------|------|---------|-------------|
| `action_type` | `string` | `?action_type=MANUAL_GATE_OPEN` | Filter logs by a specific action type enum value. |
| `user_id` | `integer` | `?user_id=3` | Filter logs by the acting user's ID. |

**Valid `action_type` values:**

| Value | Display Label |
|-------|---------------|
| `MANUAL_GATE_OPEN` | Manual Gate Open |
| `PRICE_CHANGE` | Price Rule Changed |
| `SPOT_CREATED` | Parking Spot Created |
| `SPOT_UPDATED` | Parking Spot Updated |
| `SPOT_DELETED` | Parking Spot Deleted |
| `USER_CREATED` | User Account Created |
| `USER_DEACTIVATED` | User Account Deactivated |
| `LOGIN_SUCCESS` | Successful Login |
| `LOGIN_FAILED` | Failed Login Attempt |
| `PASSWORD_CHANGED` | Password Changed |
| `TICKET_VOIDED` | Ticket Voided |
| `OCCUPANCY_RESET` | Lot Occupancy Reset |

### Response — `200 OK`

```json
[
    {
        "id": 42,
        "username": "admin1",
        "action_type": "PRICE_CHANGE",
        "action_type_display": "Price Rule Changed",
        "details": {
            "rule_id": 5,
            "old_hourly_rate": 3.00,
            "new_hourly_rate": 5.00
        },
        "ip_address": "192.168.1.100",
        "timestamp": "2026-04-06T09:15:00Z"
    },
    {
        "id": 41,
        "username": "admin1",
        "action_type": "MANUAL_GATE_OPEN",
        "action_type_display": "Manual Gate Open",
        "details": {
            "gate_id": "ENT-1",
            "reason": "Emergency vehicle"
        },
        "ip_address": "192.168.1.100",
        "timestamp": "2026-04-06T08:45:00Z"
    }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `id` | `integer` | Audit log entry primary key. |
| `username` | `string` | Username of the user who performed the action. Defaults to `"system"` if the user is `null`. |
| `action_type` | `string` | Machine-readable action type code (see table above). |
| `action_type_display` | `string` | Human-readable label for the action type. |
| `details` | `object` | Arbitrary JSON payload describing the specifics of the action (e.g., old vs. new values). |
| `ip_address` | `string \| null` | Source IP of the HTTP request that triggered the action. |
| `timestamp` | `string (ISO 8601)` | UTC timestamp of when the action occurred. |

---

## 7. TwoFactorSetupView

**Endpoint:** `POST /api/v1/auth/2fa/setup/`
**Permission:** `IsAuthenticated`, `IsAdminRole`
**Description:** Generates a fresh TOTP secret and returns a provisioning URI for authenticator apps. The secret is stored in the session temporarily — it is **not** saved to the database until [`/2fa/verify/`](#8-twofactorverifyview) succeeds.

### Request Body

No body required. Authentication via `Authorization: Bearer <access_token>` header.

### Response — `200 OK`

```json
{
    "success": true,
    "provisioning_uri": "otpauth://totp/ParkingLot%20Management%20System:admin1%40example.com?secret=JBSWY3DPEHPK3PXP&issuer=ParkingLot+Management+System",
    "secret": "JBSWY3DPEHPK3PXP",
    "message": "Scan the provisioning URI with your authenticator app, then call /2fa/verify/."
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | `boolean` | Always `true` on success. |
| `provisioning_uri` | `string` | An `otpauth://` URI that authenticator apps (e.g., Google Authenticator) can scan as a QR code. |
| `secret` | `string` | The raw Base32 TOTP secret for manual entry into an authenticator app. |
| `message` | `string` | Instructional message for the client. |

---

## 8. TwoFactorVerifyView

**Endpoint:** `POST /api/v1/auth/2fa/verify/`
**Permission:** `IsAuthenticated`, `IsAdminRole`
**Description:** Verifies the TOTP code from the authenticator app. On success, permanently saves the TOTP secret to the user record, activating 2FA. Also creates an audit log entry.

### Request Body (JSON)

```json
{
    "totp_code": "123456"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `totp_code` | `string` | ✅ Yes | Six-digit TOTP code from the authenticator app. A ±1 time-step window is allowed. |

### Response — `200 OK` (Success)

```json
{
    "success": true,
    "message": "Two-factor authentication has been activated."
}
```

### Response — `400 Bad Request` (No pending setup)

Returned if `/2fa/setup/` was never called in this session, or the session expired.

```json
{
    "success": false,
    "error": {
        "code": "INVALID_STATE",
        "message": "No pending 2FA setup found. Call /2fa/setup/ first."
    }
}
```

### Response — `400 Bad Request` (Invalid TOTP code)

```json
{
    "success": false,
    "error": {
        "code": "TOTP_INVALID",
        "message": "Invalid TOTP code. Please try again."
    }
}
```

---

## Common Error Responses

All endpoints that require authentication will return the following if the JWT is missing or invalid:

### `401 Unauthorized` (Missing/Invalid JWT)

```json
{
    "detail": "Authentication credentials were not provided."
}
```

### `403 Forbidden` (Insufficient Role)

Returned by endpoints requiring `IsAdminRole` when an Attendant tries to access them:

```json
{
    "detail": "You do not have permission to perform this action."
}
```
