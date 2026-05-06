# Track 5 - Attendant JWT Workflow Redesign

> **Status**: Approved Design
> **Date**: 2026-04-28
> **Scope**: `apps/attendant_ui`

---

## 1. Overview

This note records the approved redesign for the Attendant UI route structure and authentication workflow.

The current implementation makes `/attendant/` the dashboard route and relies on client-side `localStorage` checks to decide whether the user should stay on the page or be redirected. This creates an unrealistic experience because the dashboard is treated as the primary entry point instead of the login gateway.

The redesign keeps JWT as the authentication mechanism while restructuring the Attendant UI to behave like a real staff workflow:

- `/attendant/` becomes the single public entry point
- unauthenticated attendants see the sign-in page
- authenticated attendants are redirected into the protected work area
- dashboard, scan, and checkout pages move under a dedicated protected route namespace

## 2. Problems in the Current Design

### 2.1 Route ambiguity

The current route map makes `/attendant/` serve the dashboard directly, while `/attendant/login/` is a secondary route.

This causes confusion because users expect the base Attendant URL to act as the front door for the Attendant console, not as a protected page that only later decides whether login is required.

### 2.2 Login is optional in practice

The login template automatically redirects to `/attendant/` when an `access_token` exists in `localStorage`, even before confirming the token is still usable.

As a result:

- old browser state can bypass the intended login experience
- the login page is not consistently shown as the entry step
- the user experience feels like a direct jump into the dashboard

### 2.3 Protected pages are not clearly separated

The current URLs mix the public login page and protected work pages in the same shallow route level:

```text
/attendant/login/
/attendant/
/attendant/scan/
/attendant/checkout/
```

This works technically, but it does not communicate which routes are public and which belong to the authenticated work area.

## 3. Approved Route Structure

The Attendant UI will use the following route design:

```text
/attendant/                 -> Attendant entry point
/attendant/login/           -> Explicit login alias
/attendant/app/dashboard/   -> Protected dashboard
/attendant/app/scan/        -> Protected ticket scan page
/attendant/app/checkout/    -> Protected payment page
```

### Route intent

- `/attendant/` is the canonical entry URL given to staff
- `/attendant/login/` remains available as a direct login URL or alias
- `/attendant/app/...` is the protected work area used after successful authentication

## 4. JWT Authentication Flow

### 4.1 Entry behavior

When the user opens `/attendant/`:

1. the page checks whether JWT tokens are present
2. if no tokens exist, the sign-in form is shown
3. if tokens exist, the UI validates them by loading the current user or refreshing the access token
4. if validation succeeds, the user is redirected to `/attendant/app/dashboard/`
5. if validation fails, tokens are cleared and the sign-in form remains visible

### 4.2 Login submission

The login page continues to use:

```text
POST /api/v1/auth/login/
POST /api/v1/auth/refresh/
```

On successful login:

- save `access_token` and `refresh_token`
- optionally save lightweight user metadata from the login response
- redirect to `/attendant/app/dashboard/`

### 4.3 Protected page behavior

All pages under `/attendant/app/` will use the existing JWT helper logic:

- attach `Authorization: Bearer <token>`
- refresh the access token on `401`
- redirect back to `/attendant/` if refresh fails

## 5. Realistic Attendant Workflow

The intended staff workflow becomes:

```text
Open /attendant/
  -> sign in with username + password
  -> arrive at /attendant/app/dashboard/
  -> move to /attendant/app/scan/
  -> scan ticket and review fee
  -> move to /attendant/app/checkout/
  -> process payment
  -> return to scan for the next vehicle
```

This is closer to real operational software because the user enters through a clear authentication gate and then works inside a distinct application area.

## 6. UI and Redirect Rules

### 6.1 Public pages

The public Attendant entry pages must not render the full authenticated app shell by default.

That means:

- the login page should be a standalone view
- sidebar and work navigation should appear only inside `/attendant/app/...`

### 6.2 Redirect rules

- `/attendant/` and `/attendant/login/`
  - if authenticated: redirect to `/attendant/app/dashboard/`
  - if not authenticated: stay on login
- `/attendant/app/dashboard/`
  - if authenticated: load dashboard
  - if not authenticated: redirect to `/attendant/`
- `/attendant/app/scan/`
  - if authenticated: load scan page
  - if not authenticated: redirect to `/attendant/`
- `/attendant/app/checkout/`
  - if authenticated and pending scan data exists: load checkout
  - if authenticated but no pending scan data exists: show recovery action linking to scan
  - if not authenticated: redirect to `/attendant/`

## 7. Core Implementation Targets

The implementation should update these areas:

| File | Expected change |
|---|---|
| `apps/attendant_ui/urls.py` | Introduce entry route plus `/app/...` protected route namespace |
| `apps/attendant_ui/views.py` | Split public entry/login views from protected app views |
| `templates/base.html` | Limit the authenticated app shell to protected pages only |
| `templates/attendant/login.html` | Treat as entry/login screen and redirect only after token validation |
| `templates/attendant/dashboard.html` | Update links to `/attendant/app/dashboard/` |
| `templates/attendant/scan_ticket.html` | Update links and checkout redirect path |
| `templates/attendant/checkout.html` | Update links and recovery path |

## 8. Expected Outcome

After this redesign:

- attendants will have one stable URL to open
- the login page will no longer feel bypassed
- JWT remains the only authentication mechanism
- the work area will have a clear protected namespace
- the route structure will better match the system design and real staff usage
