# Manual Gate Operation Pages

Manual fallback UI for all four `gates/views.py` endpoints, to be used when
hardware gate controllers malfunction.

---

## Background

Currently only `TicketListView` has a frontend consumer (`dashboard.html`).
The other three endpoints — `GateEntryView`, `GateOverrideView`, and
`TicketDetailView` — have no HTML interface. These pages fill that gap.

---

## Pages to Build

### Page 1 — Manual Entry (`/attendant/app/entry/`)
**Calls:** `POST /api/v1/gates/entry/`  
**Who uses it:** Attendant (when the entry barrier hardware fails)  
**What it does:** Attendant selects vehicle type, enters gate ID and optional
plate number, submits → system reserves a spot and prints the ticket code.

Form fields:
- `vehicle_type` — dropdown: CAR / MOTORCYCLE / TRUCK
- `gate_id` — pre-filled dropdown of known gate IDs (editable fallback)
- `plate_number` — optional free text

Success (201): Display the generated `ticket_code` prominently so the attendant
can write it on a paper stub.  
Error (409 LOT_FULL): Show a clear "Lot is Full" warning.

---

### Page 2 — Ticket Lookup (`/attendant/app/ticket-lookup/`)
**Calls:** `GET /api/v1/gates/tickets/<ticket_code>/`  
**Who uses it:** Any authenticated attendant  
**What it does:** Attendant types a ticket code → display all stored details
(vehicle type, spot, entry time, status).  Useful for verifying a paper stub
when the scanner is down.

Form fields:
- `ticket_code` — text input (auto-uppercased)

Success (200): Show a detail card with all ticket fields.  
Error (404): Show "Ticket not found" with a retry prompt.

---

### Page 3 — Gate Override (`/attendant/app/override/`)
**Calls:** `POST /api/v1/gates/<gate_id>/override/`  
**Who uses it:** Admin only (enforced both by DRF `IsAdminRole` on the API and
by a client-side role check that hides the nav link for non-admins)  
**What it does:** Admin manually opens any gate (entry or exit) without issuing
a ticket — for emergencies (fire exit, VIP, stuck vehicle).

Form fields:
- `gate_id` — dropdown of known gates (editable)
- `direction` — radio: ENTRY / EXIT
- `reason` — required textarea (written to AuditLog)
- `plate_number` — optional text

Success (200): Show a green "Gate Opened" confirmation with the audit summary.  
Error (400 / 403): Show the server error message.

> [!IMPORTANT]
> The override page is accessible at the same `/attendant/` shell for
> simplicity (it reuses `base.html` + `apiFetch`). The nav link is hidden from
> the sidebar for non-admin roles using a JS role check after login, matching
> the existing pattern. The DRF backend independently enforces `IsAdminRole`.

---

## Files Changed

### New Templates
#### [NEW] `templates/attendant/manual_entry.html`
#### [NEW] `templates/attendant/ticket_lookup.html`
#### [NEW] `templates/attendant/gate_override.html`

---

### `apps/attendant_ui/views.py`
Add three new `View` subclasses (GET only — render shell templates):
- `AttendantManualEntryView` → renders `attendant/manual_entry.html`
- `AttendantTicketLookupView` → renders `attendant/ticket_lookup.html`
- `AttendantGateOverrideView` → renders `attendant/gate_override.html`

---

### `apps/attendant_ui/urls.py`
Add three new `path()` entries:
```
path("app/entry/",          AttendantManualEntryView.as_view(),   name="manual_entry"),
path("app/ticket-lookup/",  AttendantTicketLookupView.as_view(),  name="ticket_lookup"),
path("app/override/",       AttendantGateOverrideView.as_view(),  name="gate_override"),
```

---

### `templates/base.html`
Add three nav items to the sidebar `<ul>`:
- **Manual Entry** (icon E, `active_page == 'entry'`) — visible to all
- **Ticket Lookup** (icon L, `active_page == 'lookup'`) — visible to all
- **Gate Override** (icon O, `active_page == 'override'`) — hidden by JS for
  non-admin roles

---

## Implementation Order

1. `base.html` — add sidebar links first (safe, no logic change)
2. `views.py` + `urls.py` — wire up the three new shell views
3. `manual_entry.html` — Page 1 (most common fallback scenario)
4. `ticket_lookup.html` — Page 2 (read-only, lowest risk)
5. `gate_override.html` — Page 3 (admin-only, highest impact — built last)

---

## Verification Plan

### Manual Verification
- Visit each URL while logged in as attendant; confirm page loads.
- Submit Manual Entry with a valid vehicle type → confirm ticket code appears.
- Submit Ticket Lookup with a known code → confirm details card appears.
- Log in as admin; confirm Override nav link visible and form submits successfully.
- Log in as attendant; confirm Override nav link is hidden.
