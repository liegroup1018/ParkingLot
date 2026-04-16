# Track 7 — Auth Unification: Session → JWT

> **Status:** ✅ Complete
> **Date:** 2026-04-13
> **Validated:** `python manage.py check` → 0 issues

---

## 1. Motivation

Prior to this track the project ran two separate authentication schemes simultaneously:

| Scheme | Used by | Mechanism |
|---|---|---|
| JWT (Bearer token) | Attendant UI, all DRF API clients | `Authorization: Bearer <token>` header |
| Django Session | Admin UI login form | `sessionid` cookie + CSRF token |

This violated `system_design.md §5` ("lightweight JavaScript to communicate with DRF APIs"), duplicated TOTP validation logic, and introduced two independent auth planes with different logout semantics.

Track 7 eliminates the session-based path entirely, leaving a single JWT auth plane for all clients.

---

## 2. Files Changed

### `apps/admin_ui/views.py` — **Rewritten**

| Before | After |
|---|---|
| `AdminLoginView(View)` with `authenticate()` / `login()` / `pyotp.TOTP` | `AdminLoginView(TemplateView)` — pure renderer, no auth logic |
| `AdminDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView)` | `AdminDashboardView(TemplateView)` — pure renderer, session guard removed |

All imports of `pyotp`, `authenticate`, `login`, `messages`, `UserPassesTestMixin`, `LoginRequiredMixin`, and `UserRole` have been removed.

### `apps/admin_ui/templates/admin_ui/login.html` — **Rewritten**

| Before | After |
|---|---|
| `<form method="POST" action="{% url 'admin_login' %}">` Django form POST | `<form id="login-form">` intercepted by JS — no native submission |
| `{% csrf_token %}` | Removed — not needed for `fetch()` with JSON body |
| `{% if messages %}` Django messages framework | `<div id="error-alert">` populated by JS |
| Server-side redirect to dashboard | Client-side `window.location.replace('/admin-dashboard/')` |

New JavaScript logic:
1. **Guard** — redirects to dashboard immediately if `admin_access_token` already in `sessionStorage`
2. **Submit handler** — calls `POST /api/v1/auth/login/` (the same JWT endpoint used by the Attendant UI), validates `role === 'ADMIN'` in the response, stores `access` and `refresh` tokens in `sessionStorage`
3. **Error display** — parses the API error envelope `{ "error": { "message": "..." } }` and falls back to `detail` / `non_field_errors`

### `apps/admin_ui/templates/admin_ui/dashboard.html` — **Rewritten**

| Before | After |
|---|---|
| `{{ request.user.username }}` (server-rendered via session) | `<span id="nav-username">` populated by `GET /api/v1/auth/users/me/` |
| `<a href="/api/v1/auth/logout/">Sign Out</a>` (broken — was a GET to a POST endpoint) | `<button onclick="handleLogout()">` — properly POSTs refresh token to `/api/v1/auth/logout/` then clears sessionStorage |
| `fetch(url, { credentials: 'same-origin' })` — relied on session cookie | `apiFetch(url)` — attaches `Authorization: Bearer <token>` header |
| `'X-CSRFToken': csrfToken` on pricing PUT | Removed — not needed with JWT |
| No auth guard | Immediate redirect to `/admin-dashboard/login/` if no token in `sessionStorage` |

New JavaScript additions:
- **`apiFetch()`** — mirrors the Attendant UI's pattern; attaches Bearer token, silently refreshes on 401, redirects to login on refresh failure
- **`tryRefresh()`** — calls `POST /api/v1/auth/refresh/` and updates stored tokens
- **`handleLogout()`** — calls `POST /api/v1/auth/logout/` with the refresh token (blacklisting it server-side), clears `sessionStorage`, redirects to login

### `config/settings.py` — **Modified**

```diff
-LOGIN_URL = "/admin-dashboard/login/"
+# LOGIN_URL removed (Track 7): no session-based views remain.
```

```diff
 REST_FRAMEWORK = {
     "DEFAULT_AUTHENTICATION_CLASSES": (
+        # JWT-only (Track 7): SessionAuthentication removed — all clients
+        # (Attendant UI + Admin UI) now authenticate via Bearer token.
         "rest_framework_simplejwt.authentication.JWTAuthentication",
-        "rest_framework.authentication.SessionAuthentication",
     ),
```

---

## 3. Architecture After Track 7

```
                     ┌────────────────────────────────────────┐
                     │         Django Backend                  │
                     │                                         │
  Attendant Browser ─►                                         │
    (JavaScript)     │  POST /api/v1/auth/login/               │
                     │  └─► ParkingTokenObtainPairSerializer   │
  Admin Browser    ──►      (JWT + TOTP validated once)        │
    (JavaScript)     │                                         │
                     │  All protected views:                   │
                     │  DRF JWTAuthentication                  │
                     │  + IsAdminRole / IsAttendantRole        │
                     │                                         │
                     │  Single auth plane, two roles.          │
                     └────────────────────────────────────────┘
```

---

## 4. What Was NOT Changed

- `apps/accounts/views.py` — `LoginView` (JWT endpoint) unchanged; it already handled both roles correctly including TOTP.
- `apps/attendant_ui/views.py` — already followed the correct pattern; untouched.
- `apps/attendant_ui/templates/` — unchanged.
- All DRF API views (inventory, gates, payments) — unchanged; their `IsAdminRole` / `IsAttendantRole` / `IsAuthenticated` guards now enforce auth via JWT only.
- Database migrations — no model changes required.

---

## 5. Token Storage Decision

| UI | Storage | Rationale |
|---|---|---|
| Attendant UI | `localStorage` | Already implemented in Track 5; survives page reload which is important for a POS workstation |
| Admin UI | `sessionStorage` | Higher privilege; tab-scoped storage clears automatically when the tab/browser closes, reducing the window for token theft |

---

## 6. TOTP Validation — Single Source of Truth

TOTP is now validated in exactly one place: `ParkingTokenObtainPairSerializer` in `apps/accounts/serializers.py`. The duplicate TOTP block that previously existed in `AdminLoginView` (lines 41–44 of the old `apps/admin_ui/views.py`) has been removed with the view itself.

---

## 7. Verification

```bash
python manage.py check
# System check identified no issues (0 silenced).
```
