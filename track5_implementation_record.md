# Track 5 — Attendant UI & Frontend Integration

> **Status**: ✅ Complete  
> **Date**: 2026-03-29  
> **Validated**: `python manage.py check` → 0 issues

---

## 1. Overview

Track 5 implements the **Attendant-facing HTML interface** for the Parking Lot Management System. Following the API-first methodology defined in `system_design.md §5`, these pages consume the DRF API endpoints built in Tracks 1–4 using client-side `fetch()` with JWT tokens.

## 2. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `static/css/style.css` | Complete design system — dark theme, glassmorphism, micro-animations |
| `templates/base.html` | Base template with sidebar nav, JWT token management, auto-refresh |
| `templates/attendant/login.html` | Login page with JWT storage & redirect |
| `templates/attendant/dashboard.html` | Real-time occupancy dashboard with progress bars & ticket table |
| `templates/attendant/scan_ticket.html` | Ticket scanning → fee calculation interface |
| `templates/attendant/checkout.html` | Payment checkout with cash change calculator & gate-open animation |
| `apps/attendant_ui/__init__.py` | Package init |
| `apps/attendant_ui/views.py` | Django views serving the templates (4 views) |
| `apps/attendant_ui/urls.py` | URL routing under `/attendant/` |

### Modified Files

| File | Change |
|---|---|
| `config/settings.py` | Added `STATICFILES_DIRS = [BASE_DIR / "static"]` |
| `config/urls.py` | Added `path("attendant/", include("apps.attendant_ui.urls"))` |

## 3. Architecture Decisions

### 3.1 Client-Side JWT Authentication
- Tokens stored in `localStorage` (`access_token`, `refresh_token`)
- Global `apiFetch()` helper automatically attaches `Bearer` token
- Automatic token refresh on 401 responses
- Redirect to `/attendant/login/` when no valid tokens exist

### 3.2 API Integration Map

| UI Page | API Endpoint | Method | Purpose |
|---|---|---|---|
| Login | `/api/v1/auth/login/` | POST | Obtain JWT tokens |
| Login | `/api/v1/auth/refresh/` | POST | Refresh access token |
| Dashboard | `/api/v1/spots/occupancy/` | GET | Real-time lot occupancy |
| Dashboard | `/api/v1/gates/tickets/?status=OPEN` | GET | Recent open tickets |
| Dashboard | `/api/v1/auth/users/me/` | GET | Current user display |
| Scan Ticket | `/api/v1/tickets/scan` | POST | Fee calculation |
| Checkout | `/api/v1/payments` | POST | Process payment |

### 3.3 Data Flow: Scan → Checkout

```
[Scan Page] → POST /tickets/scan → response.amount_owed
    ↓
sessionStorage.setItem('pending_ticket', JSON.stringify(scanData))
    ↓
[Checkout Page] → reads sessionStorage → displays summary
    ↓
POST /payments { ticket_id, amount_paid, method }
    ↓
Success → gate-open animation + receipt
```

### 3.4 Design System Tokens

The CSS design system (`static/css/style.css`) uses CSS custom properties for theming:

- **Surfaces**: 5-tier dark backgrounds (`#0f1117` → `#232738`)
- **Accent palette**: Indigo gradient (`#6366f1` → `#a78bfa`)
- **Status colors**: Success (green), Warning (amber), Danger (red)
- **Typography**: Inter (UI) + JetBrains Mono (data/code)
- **Animations**: `fadeSlideUp`, `spin`, `pulse` keyframes
- **Responsive**: Sidebar collapses at 768px, cards reflow at 480px

## 4. UI Feature Summary

### 4.1 Login Page (`/attendant/login/`)
- Username + password form
- JWT token acquisition and storage
- Error display with shimmer animation
- Auto-redirect if already authenticated

### 4.2 Dashboard (`/attendant/`)
- **Occupancy Cards**: One per spot size (COMPACT, REGULAR, OVERSIZED) + TOTAL
  - Shows available count, occupied/total, color-coded progress bar
  - Green (<60%), Amber (60-85%), Red (>85%)
- **Recent Tickets Table**: Lists open tickets with code, vehicle, spot, status badge, entry time
- **Auto-refresh**: Occupancy every 15s, tickets every 30s

### 4.3 Scan Ticket (`/attendant/scan/`)
- Large input for ticket code with uppercase transform
- Calls `POST /api/v1/tickets/scan`
- Displays: amount owed, vehicle type, duration, spot size, hourly rate
- "Proceed to Payment" saves data to `sessionStorage` and navigates to checkout

### 4.4 Checkout (`/attendant/checkout/`)
- Left panel: Ticket summary (code, vehicle, spot, duration, rate, total)
- Right panel: Payment method selector (Cash / Credit / Mobile)
- Cash mode: "Cash Tendered" input with live change calculator
- Success: Gate-open animation (pulsing green checkmark) + printable receipt
- "Process Next Vehicle" resets the flow

## 5. URL Configuration

```
/attendant/login/        → AttendantLoginView     (login.html)
/attendant/              → AttendantDashboardView  (dashboard.html)
/attendant/scan/         → AttendantScanTicketView (scan_ticket.html)
/attendant/checkout/     → AttendantCheckoutView   (checkout.html)
```

## 6. Verification

```bash
D:\Anaconda\python.exe manage.py check
# System check identified no issues (0 silenced).
```

> **Note**: `runserver` requires MySQL to be running. The DB connection error
> (`Access denied for user 'root'@'localhost'`) is a credentials issue, not
> a code issue. Once the `.env` DB password is correct, the server will serve
> all pages at the routes listed above.
