# Track 4 Implementation Record — Pricing Engine & Exit Flow

**Status:** ✅ COMPLETE  
**Completed:** 2026-03-24

---

## Deliverables

### `apps/payments/` — New Django Application

| File | Purpose |
|---|---|
| `__init__.py` | Package marker |
| `apps.py` | `PaymentsConfig` AppConfig |
| `models.py` | Task 4.1 — `PricingRule` and `Payment` models |
| `serializers.py` | Request/response validation for fee calculation and payments |
| `views.py` | `TicketScanView` and `PaymentProcessView` |
| `urls.py` | Route definitions for `/api/v1/tickets/scan` and `/api/v1/payments` |
| `migrations/` | Schema and Data migrations including initial default PricingRules |

---

## Task 4.1 — Data Models

### `PricingRule` Model
**Table:** `payments_pricing_rules`

| Column | Type | Notes |
|---|---|---|
| `id` | BigAutoField PK | — |
| `vehicle_type` | `VARCHAR(15)` | `MOTORCYCLE / CAR / TRUCK` |
| `spot_size` | `VARCHAR(15)` | `COMPACT / REGULAR / OVERSIZED` |
| `time_start` | `TIME` | Start time of this pricing rule validity |
| `time_end` | `TIME` | End time of this rule validity |
| `hourly_rate` | `DECIMAL(6,2)` | Surcharge rate per hour |
| `max_daily_rate` | `DECIMAL(6,2)` | Absolute max daily cap |
| `is_active` | `BOOLEAN` | Toggles rule availability |
| `created_at` | `DATETIME` | auto_now_add |
| `updated_at` | `DATETIME` | auto_now |

**Constraints & Indexes:**
- Composite index usage combined with validation through `chk_pricing_vehicle_type_valid` and `chk_pricing_spot_size_valid`.

### `Payment` Model
**Table:** `payments_transactions`

| Column | Type | Notes |
|---|---|---|
| `id` | BigAutoField PK | — |
| `ticket_id` | FK → `gates_tickets` | Protected deletion |
| `processed_by_id` | FK → `accounts_users` | Set null to preserve history |
| `amount` | `DECIMAL(8,2)` | Total amount paid |
| `payment_method` | `VARCHAR(15)` | `CASH / CREDIT / MOBILE` |
| `payment_time` | `DATETIME` | auto_now_add |
| `status` | `VARCHAR(15)` | `SUCCESS / FAILED` |

---

## Task 4.2 — Seed Data

Utilized Django Data Migrations (`apps/payments/migrations/0002_seed_pricing_rules.py`) to systematically populate initial default pricing rules:
- **Motorcycle**: Compact ($2/hr, max $20), Regular ($3/hr, max $30), Oversized ($4/hr, max $40)
- **Car**: Regular ($5/hr, max $40), Oversized ($6/hr, max $50)
- **Truck**: Oversized ($10/hr, max $80)

---

## Task 4.3 — `POST /api/v1/tickets/scan`

**Permission:** `IsAuthenticated`

**Request:** `{"ticket_code": "..."}`

**Service Logic (`TicketScanView`):**
1. Validate ticket exists and is `OPEN` (Returns 400 if already paid/voided).
2. Compute `duration_hours` = `math.ceil((now - ticket.entry_time) / 3600))`. Minimal cap set at 1 hour.
3. Lookup active `PricingRule` matching `ticket.vehicle_type` and `ticket.assigned_size`.
4. Calculate fee = `min(duration_hours * hourly_rate, max_daily_rate)`.
5. Return JSON containing `duration_hours`, `hourly_rate`, `max_daily_rate`, and `amount_owed`.

---

## Task 4.4 — `POST /api/v1/payments`

**Permission:** `IsAuthenticated`

**Request:**
```json
{
  "ticket_id": "<ticket_code>",
  "amount_paid": "10.00",
  "method": "CREDIT"
}
```

**Service Logic (`PaymentProcessView`):**
1. Validate ticket is `OPEN`.
2. Persist `Payment` model record bridging `ticket_id`, `amount_paid`, and `processed_by`.
3. Update ticket `status = PAID` and `exit_time = now()`.
4. **OCC Restitution:** Trigger Track 2's `LotOccupancy.attempt_release(ticket.assigned_size)` atomically returning an spot counting slot to the corresponding pool.
5. Return 201 Created acknowledging success exit gate procedure.

---

## Framework Wiring

- `config/settings.py` → `LOCAL_APPS` ← `"apps.payments.apps.PaymentsConfig"` added
- `config/urls.py` → `path("api/v1/", include("apps.payments.urls"))` added
  - Exposes sub-routes `/tickets/scan` and `/payments` underneath `/api/v1/`

---

## Design Decisions

1. **Duration Fallback** — Any partial hour usage under 1 hour maps strictly to baseline 1-hour charge to prevent fractional negative billing bounds.
2. **OCC Decoupling Strategy** — Delegated releasing spots fully back to the `inventory_lot_occupancy` table logic leveraging internal classmethods established historically in Track 2.
3. **Audit Continuity** — Similar to `Gates` tickets, `Payment.processed_by` operates via `SET_NULL` ensuring accurate monetary metrics remain structurally intact in events of user termination.
