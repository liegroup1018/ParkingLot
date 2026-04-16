# Track 8 - Auth Audit Completion (JWT Logout Signal)

> **Status:** Complete  
> **Date:** 2026-04-16  
> **Validated:** `python manage.py check` -> 0 issues

---

## 1. Motivation

Track 1 introduced signal-driven authentication auditing (`LOGIN_SUCCESS`, `LOGIN_FAILED`) and Track 7 unified all clients onto JWT auth.  
However, JWT logout (`POST /api/v1/auth/logout/`) blacklisted refresh tokens without emitting a corresponding logout signal, so logout events were not recorded in `AuditLog`.

This track closes that gap so logout is audited with the same event-driven pattern used for other IAM security events.

Design alignment:
- `prd.md` section 4.2 requires sensitive security actions to be permanently logged.
- `system_design.md` section 1.1 and the `AuditLogs` design require a complete audit trail for IAM behavior.
- `track1_implementation_record.md` defines signals as the primary mechanism for auth-related audit events.

---

## 2. Files Changed

### `apps/accounts/models.py`

- Added a new audit action enum value:
  - `AuditActionType.LOGOUT = "LOGOUT"`

Why:
- Keeps logout event typing explicit and filterable in audit queries.

### `apps/accounts/signals.py`

- Imported Django `user_logged_out`.
- Added receiver:
  - `log_logout(sender, request, user, **kwargs)`
  - Writes `AuditLog` with:
    - `action_type=AuditActionType.LOGOUT`
    - `user=<current user>`
    - `details={"username": <username>}`
    - `ip_address` extracted via existing `_get_client_ip()`

Why:
- Maintains the same separation-of-concerns pattern as login signals.
- Preserves centralized, consistent audit behavior.

### `apps/accounts/views.py`

- Imported `user_logged_out` signal.
- In `LogoutView.post()`, after successful refresh-token blacklisting:
  - `user_logged_out.send(sender=request.user.__class__, request=request, user=request.user)`

Why:
- JWT logout does not call Django session `logout()`, so `user_logged_out` is not emitted automatically.
- Explicit dispatch ensures signal receivers run in JWT-only architecture.

### `apps/accounts/tests.py`

- Updated `LogoutViewTest.test_logout_blacklists_token`:
  - Asserts one `AuditLog` row is created with:
    - `action_type=AuditActionType.LOGOUT`
    - `user=self.user`

Why:
- Locks in behavior with regression coverage.

---

## 3. Behavioral Result

After this track:
1. Client calls `POST /api/v1/auth/logout/` with refresh token.
2. Server blacklists refresh token.
3. Server emits `user_logged_out`.
4. Signal receiver persists `LOGOUT` event into `accounts_audit_logs`.
5. Admin audit timeline now includes explicit logout records (with actor + IP).

---

## 4. Migration Impact

- No schema migration required.
- Reason: `AuditActionType` is implemented as Django `TextChoices` for an existing `CharField`; adding a new allowed value does not alter DB schema.

---

## 5. Verification

Executed:

```bash
python manage.py check
```

Result:
- `System check identified no issues (0 silenced).`

Test note:
- The logout audit assertion is added to `apps/accounts/tests.py`.
- Full DB-backed test execution depends on local MySQL credentials in this environment.

