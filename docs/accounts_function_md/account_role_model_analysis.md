# Account Role Model Analysis

Date: 2026-05-27

## Existing Problems

The product and system documents describe human staff roles as Parking Attendants and Management Admins, while the running Django system also has a third operational account type: Django superusers.

`apps/accounts/models.py` currently models only `ADMIN` and `ATTENDANT` in `UserRole`. At the same time, `CustomUserManager.create_superuser()` sets `is_superuser=True` and assigns `role=ADMIN`. This creates several problems:

- Superusers cannot be distinguished from normal management admins by the `role` field or JWT role claim.
- Code that checks `role == ADMIN` grants access to admins but only includes superusers because they are mislabeled as admins.
- The string representation and API read serializers report superusers as "Management Admin", which hides an important privilege difference.
- Future admin UI filters, audit review, and incident response cannot reliably answer "which accounts are true superusers?"
- The staff creation API exposes the `role` field, so once `SUPERUSER` exists it must explicitly reject creating that role through the normal admin-managed staff endpoint.

## Design Options

### Option 1: Keep Superuser As A Boolean Only

Leave `UserRole` as `ADMIN | ATTENDANT` and treat `is_superuser=True` as a separate Django-only permission flag.

This is the smallest database change, but it keeps the model and token contract ambiguous because superusers continue to appear as admins in role-based APIs.

### Option 2: Add `SUPERUSER` To `UserRole`

Add `SUPERUSER` as an explicit role choice and keep Django's built-in `is_superuser` flag as the permission bypass flag. New superusers receive `role=SUPERUSER`, existing superuser rows are migrated to that role, and admin-only permissions allow both `ADMIN` and `SUPERUSER`.

This reflects the three account types directly while preserving Django's permission system.

### Option 3: Split Staff Role From Privilege Level

Replace `role` with two fields, such as `staff_role` and `privilege_level`, where superuser is a privilege level rather than a staff role.

This is more normalized, but it is larger than the current need and would touch more serializers, permission classes, migrations, and UI assumptions.

## Recommended Solution

Use Option 2.

The project already has a simple RBAC model based on one `role` field. Adding `SUPERUSER` keeps that API stable, makes JWT claims truthful, and avoids a broader redesign. Django's `is_superuser` remains the source of full framework-level privileges, while `role=SUPERUSER` becomes the application-level account type used for filtering, display, and API authorization decisions.

## Implementation Plan

- Add `UserRole.SUPERUSER = "SUPERUSER", "System Superuser"`.
- Add `User.is_system_superuser` as an explicit helper that requires both `role=SUPERUSER` and Django's `is_superuser=True`.
- Change `CustomUserManager.create_superuser()` to default `role` to `SUPERUSER`.
- Update admin-only permission checks so both Management Admins and System Superusers can access admin endpoints.
- Update combined staff permission checks so all three recognized account types are allowed where appropriate.
- Add serializer validation that rejects `SUPERUSER` in the normal staff creation API.
- Add a migration that updates existing `is_superuser=True` users to `role=SUPERUSER`.
- Update tests to lock in the three account types and prevent staff API superuser creation.

## Expected Result

After the change, the model will accurately reflect:

| Account type | `role` | Django flags | Intended use |
|---|---|---|---|
| Parking Attendant | `ATTENDANT` | `is_superuser=False` | Exit-gate operations and payments |
| Management Admin | `ADMIN` | `is_superuser=False` | Management dashboard, pricing, reports, staff management |
| System Superuser | `SUPERUSER` | `is_staff=True`, `is_superuser=True` | Emergency/root administration through Django and privileged APIs |

## Implementation Result

Implemented on 2026-05-27.

- `UserRole` now includes `SUPERUSER`.
- `create_superuser()` now defaults new superusers to `role=SUPERUSER`.
- Existing database rows with `is_superuser=True` are promoted to `role=SUPERUSER` by migration `0003_add_superuser_role`.
- `User.is_system_superuser` distinguishes true system superusers from ordinary management admins.
- `User.requires_2fa` applies 2FA enforcement to management admins and system superusers after a TOTP secret is configured.
- Admin-level DRF permissions now allow management admins and true system superusers.
- The normal staff creation API rejects `role=SUPERUSER`; superusers remain a `createsuperuser` workflow.
- `totp_code` is now an explicit serializer field so admin 2FA login can actually receive the submitted OTP.

## Verification

```text
python manage.py test apps.accounts -v 2
Result: 25 tests ran, OK

python manage.py check
Result: System check identified no issues (0 silenced).
```
