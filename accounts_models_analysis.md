# Accounts Models Analysis

This document provides a comprehensive analysis of all classes defined in `apps/accounts/models.py`, covering their primary functions, data members, and methods.

---

## 1. `UserRole` (TextChoices)
**Primary Function:** Acts as an enumeration to strictly define the Role-Based Access Control (RBAC) tiers available in the system.

### Data Members
| Member | Value | Purpose |
| :--- | :--- | :--- |
| `ADMIN` | `"ADMIN"` | Management Admin role. Grants full access to reporting, pricing structures, and user management. |
| `ATTENDANT` | `"ATTENDANT"` | Parking Attendant role. Grants restricted access limited to scanning tickets and processing payments. |

---

## 2. `AuditActionType` (TextChoices)
**Primary Function:** Acts as a semantic dictionary of every trackable event in the system. Used to populate the `action_type` field of an `AuditLog`.

### Data Members
| Event Category | Values | Purpose |
| :--- | :--- | :--- |
| **Operational** | `MANUAL_GATE_OPEN`, `TICKET_VOIDED`, `OCCUPANCY_RESET` | Tracks actions that affect the physical lot or active ticket statuses. |
| **Financial / Configuration** | `PRICE_CHANGE`, `SPOT_CREATED`, `SPOT_UPDATED`, `SPOT_DELETED` | Tracks critical system configuration and financial rule changes. |
| **Authentication & IAM** | `USER_CREATED`, `USER_DEACTIVATED`, `LOGIN_SUCCESS`, `LOGIN_FAILED`, `PASSWORD_CHANGED` | Tracks security, session, and user lifecycle events. |

---

## 3. `User` (Extends `AbstractUser`)
**Primary Function:** Represents a human staff member (Admin or Attendant) authenticating into the system. By extending Django's built-in `AbstractUser`, it inherently supports passwords, sessions, groups, and permissions, but is augmented with RBAC and 2FA features specific to the Parking Lot system.

### Data Members (Extensions over AbstractUser)
| Data Member | Type | Purpose & Meaning |
| :--- | :--- | :--- |
| `role` | `CharField` | Uses the `UserRole` choices. Indexed natively (`db_index=True`) to allow extremely fast privilege checks when querying users. Defaults to `ATTENDANT`. |
| `two_factor_secret` | `CharField` | Stores the Base32 TOTP (Time-Based One-Time Password) secret used by Authenticator apps (e.g., Google Authenticator). A blank string implies 2FA has not been configured yet. |

### Function Members (Properties & Methods)
| Member | Purpose & Meaning |
| :--- | :--- |
| `is_admin` | (Property) Returns `True` if the user's role is `UserRole.ADMIN`. |
| `is_attendant` | (Property) Returns `True` if the user's role is `UserRole.ATTENDANT`. |
| `has_2fa_configured` | (Property) Checks if `two_factor_secret` is populated and returns a boolean natively representing 2FA status. |
| `__str__()` | Returns a clean string combining the username and their human-readable role (e.g., `admin1 (Management Admin)`). |

---

## 4. `AuditLog` (Extends `models.Model`)
**Primary Function:** An immutable, append-only security ledger enforcing strict accountability across the application as demanded by PRD §4.2.

### Data Members
| Data Member | Type | Purpose & Meaning |
| :--- | :--- | :--- |
| `user` | `ForeignKey` | The user who initiated the action. Uses `on_delete=models.SET_NULL` to guarantee audit trail preservation if the user account is deleted. |
| `action_type` | `CharField` | Semantic label categorized by `AuditActionType`. Heavily indexed. |
| `details` | `JSONField` | Arbitrary payload containing the "old vs new" values necessary to understand *what* exactly changed. |
| `ip_address` | `GenericIPAddressField` | Original HTTP request IP. |
| `timestamp` | `DateTimeField` | Auto-stamped UTC time of the event. Indexed for ORDER BY sorting. |
| `objects` | `AuditLogManager` | A custom manager enforcing the business rule that logs can only be created via a strictly-typed `.log_action()` method. |

### Function Members
| Member | Purpose & Meaning |
| :--- | :--- |
| `__str__()` | Formatted read-out combining timestamp, username, and action type for server terminal formatting. |
