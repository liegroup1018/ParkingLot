# Track 3 Implementation Record — Entry Gates & Hardware Integration

**Status:** ✅ COMPLETE  
**Completed:** 2026-03-23

---

## Deliverables

### `apps/gates/` — New Django Application

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `apps.py` | `GatesConfig` AppConfig |
| `models.py` | Task 3.1 — `Ticket` model |
| `serializers.py` | Request/response validation |
| `services.py` | OCC retry logic (Task 3.2) + override audit (Task 3.3) |
| `views.py` | All 4 API views |
| `urls.py` | Route definitions |
| `admin.py` | Django Admin with bulk-void action |
| `tests.py` | 30+ test cases |
| `migrations/0001_initial.py` | Hand-written migration |

---

## Task 3.1 — `Ticket` Model

**Table:** `gates_tickets`

| Column | Type | Notes |
|---|---|---|
| `id` | BigAutoField PK | — |
| `ticket_code` | `VARCHAR(20) UNIQUE` | 12-char uppercase alphanumeric, auto-generated |
| `vehicle_type` | `VARCHAR(15)` | `MOTORCYCLE / CAR / TRUCK` |
| `assigned_size` | `VARCHAR(10)` | `COMPACT / REGULAR / OVERSIZED` (may differ from preferred — overflow) |
| `status` | `VARCHAR(10)` | `OPEN → PAID → VOIDED` |
| `entry_time` | `DATETIME` | auto_now_add |
| `exit_time` | `DATETIME NULL` | set on payment (Track 4) |
| `issued_by_id` | FK → `accounts_users` | `SET_NULL` — audit history preserved if attendant deleted |

**Indexes:**
- `UNIQUE` on `ticket_code`
- `idx_tickets_status_entry` — `(status, entry_time)` — abandoned-ticket scan (Track 6)
- `idx_tickets_vehicle_entry` — `(vehicle_type, entry_time)` — revenue analytics

**CheckConstraints (DB-level enum guards):**
- `chk_ticket_vehicle_type_valid`
- `chk_ticket_assigned_size_valid`
- `chk_ticket_status_valid`

**`_generate_code()`** — `random.choices` over 36-char alphabet × 12 = ~2.2 × 10¹⁸ key space; uniqueness enforced at DB level.

---

## Task 3.2 — `POST /api/v1/gates/entry` + OCC Flow

### Service Layer (`services.py → EntryService`)

```
Request body  →  GateEntrySerializer validates vehicle_type / gate_id / plate_number
                         ↓
EntryService.process_entry(vehicle_type, gate_id, plate_number, user)
  │
  ├─ LotOccupancy.available_size_for_vehicle(vehicle_type)
  │    Returns first size from VEHICLE_SPOT_PRIORITY with remaining capacity
  │    Returns None → raise LotFullError (→ 409 LOT_FULL)
  │
  └─ OCC retry loop (up to GATE_OCC_MAX_RETRIES = 3):
       ├─ LotOccupancy.available_size_for_vehicle()  — re-read (fresher than pre-check)
       │    None → raise LotFullError
       │
       ├─ LotOccupancy.attempt_reserve(size)         — CAS UPDATE
       │    True  → _create_ticket() @ atomic        → return Ticket
       │    False → log OCC conflict, retry
       │
       └─ All retries exhausted → raise OCCConflictError (→ 409 OCC_CONFLICT)
```

**CAS UPDATE (from Track 2 `attempt_reserve`):**
```sql
UPDATE inventory_lot_occupancy
   SET current_count = current_count + 1,
       version       = version + 1
 WHERE spot_size     = 'REGULAR'
   AND version       = <read_version>
   AND current_count < total_capacity;
-- rows_affected = 0 → conflict; rows_affected = 1 → success
```

**OCC retry config:**  
`GATE_OCC_MAX_RETRIES = 3` — overridable in `settings.py`.

**Response on 201:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "ticket_code": "A3F9QK2LPX7Y",
    "vehicle_type": "CAR",
    "assigned_size": "REGULAR",
    "status": "OPEN",
    "entry_time": "2026-03-23T09:50:00Z",
    "exit_time": null,
    "issued_by": 2,
    "issued_by_username": "gate_attendant"
  }
}
```

**Response on 409 (lot full):**
```json
{"success": false, "code": "LOT_FULL", "message": "No available spot for vehicle type: CAR"}
```

**Response on 409 (OCC conflict):**
```json
{"success": false, "code": "OCC_CONFLICT", "message": "OCC reserve failed after 3 attempts. Gate client should retry."}
```

---

## Task 3.3 — `POST /api/v1/gates/<gate_id>/override`

**Permission:** `IsAdminRole` (403 if Attendant).

**Service (`OverrideService.process_override`):**
1. Validate `reason` (min 5 chars), `direction` (ENTRY/EXIT).
2. Write `AuditLog` row with `action_type=MANUAL_GATE_OPEN`:
   ```json
   {
     "gate_id":      "GATE-NORTH-01",
     "direction":    "ENTRY",
     "reason":       "Emergency ambulance access",
     "plate_number": "AMB 001"
   }
   ```
3. Emit `logger.warning()` for ops monitoring.
4. Return 200 `{ success: true, data: { gate_id, direction, opened_by, reason } }`.

**No Ticket is created. No OCC is touched.** Override is purely a logged gate-signal.

---

## Supporting Endpoints (read-only)

| Endpoint | Permission | Purpose |
|---|---|---|
| `GET /api/v1/gates/tickets/` | Any auth | List all tickets; filter `?status=` / `?vehicle_type=` |
| `GET /api/v1/gates/tickets/<code>/` | Any auth | Lookup by ticket code (used by exit gate in Track 4) |

---

## Framework Wiring

- `config/settings.py` → `LOCAL_APPS` ← `"apps.gates.apps.GatesConfig"` added
- `config/urls.py` → `path("api/v1/gates/", include("apps.gates.urls"))` added

---

## Test Coverage

| Test Class | Cases | What is tested |
|---|---|---|
| `TicketModelTest` | 4 | Code generation, uniqueness, default status, `__str__` |
| `EntryServiceTest` | 8 | Happy path, OCC reserve count, lot full, overflow (3 scenarios), always-conflict raises `OCCConflictError`, retry-on-2nd-attempt |
| `OverrideServiceTest` | 3 | Audit log persisted, summary dict returned, no ticket created |
| `GateEntryAPITest` | 8 | Attendant/Admin success, 401 unauth, 409 lot full, 409 OCC conflict, 400 bad vehicle type, 400 missing gate_id, OCC count increment |
| `GateOverrideAPITest` | 6 | Admin 200, Attendant 403, audit log written, short reason 400, invalid direction 400, no ticket created |
| `TicketListAPITest` | 4 | List all, filter by status, filter by vehicle_type, 401 unauth |
| `TicketDetailAPITest` | 2 | Found by code, 404 not found |

---

## Design Decisions

1. **Service layer isolation** — `EntryService` and `OverrideService` live in `services.py`, not in views. Views are thin pass-throughs; all business logic is unit-testable without HTTP.

2. **Two-phase lot check** — `available_size_for_vehicle()` is called *before* the retry loop (fail fast) AND *inside* each iteration (re-read captures concurrent draining by other gates).

3. **`GATE_OCC_MAX_RETRIES`** — configurable from `settings.py` via `getattr(settings, "GATE_OCC_MAX_RETRIES", 3)`. Default 3 balances correctness vs. latency under high load.

4. **Ticket `_create_ticket` wrapped with `@transaction.atomic`** — ensures that if ticket DB write fails, the OCC slot remains decremented (caller responsible for compensation in Track 4 rollback scenarios).

5. **`issued_by` FK with `SET_NULL`** — matches `AuditLog.user` pattern from Track 1: deleting an attendant account never cascades to destroy ticket history.

6. **`ticket_code` uppercased in `TicketDetailView`** — `ticket_code.upper()` tolerates barcode-scanner lowercase output: same code `a3f9qk2lpx7y` and `A3F9QK2LPX7Y` resolve identically.
