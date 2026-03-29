# Track 4: Pricing Engine & Exit Flow — Implementation Record

> **Status**: ✅ Complete (reviewed & patched 2026-03-29)  
> **Validated**: `python manage.py check` → 0 issues

---

## 1. Goal

Implement dynamic fee calculation based on parking duration, vehicle type, and spot size. Process payments, close tickets (OPEN → PAID), and atomically restore lot occupancy via the OCC release pattern established in Track 2.

---

## 2. Files Created / Modified

### New Files

| File | Purpose |
|---|---|
| `apps/payments/models.py` | `PricingRule` and `Payment` models with check constraints |
| `apps/payments/serializers.py` | `TicketScanSerializer`, `PaymentCreateSerializer` |
| `apps/payments/views.py` | `TicketScanView`, `PaymentProcessView` |
| `apps/payments/urls.py` | Routes: `/tickets/scan`, `/payments` |
| `apps/payments/admin.py` | Admin registration for `PricingRule` (inline-editable) and `Payment` |
| `apps/payments/apps.py` | AppConfig (`apps.payments`) |
| `apps/payments/migrations/0001_initial.py` | Schema migration |
| `apps/payments/migrations/0002_seed_pricing_rules.py` | Data migration seeding default pricing rules |

### Modified Files

| File | Change |
|---|---|
| `config/urls.py` | Added `path("api/v1/", include("apps.payments.urls"))` |

---

## 3. Data Models

### 3.1 PricingRule

Determines the hourly rate and daily cap for a given vehicle/spot combination.

| Field | Type | Purpose |
|---|---|---|
| `vehicle_type` | CharField(choices) | MOTORCYCLE, CAR, TRUCK |
| `spot_size` | CharField(choices) | COMPACT, REGULAR, OVERSIZED |
| `time_start` / `time_end` | TimeField | Time-of-day window for this rule |
| `hourly_rate` | Decimal(6,2) | Price per hour |
| `max_daily_rate` | Decimal(6,2) | Cap per 24-hour period |
| `is_active` | Boolean | Soft-delete / toggle |

**Constraints**: `chk_pricing_vehicle_type_valid`, `chk_pricing_spot_size_valid`

### 3.2 Payment

Records each completed payment transaction.

| Field | Type | Purpose |
|---|---|---|
| `ticket` | FK → Ticket | Links to the parking session |
| `processed_by` | FK → User | Attendant who processed (SET_NULL) |
| `amount` | Decimal(8,2) | Amount paid |
| `payment_method` | CharField(choices) | CASH, CREDIT, MOBILE |
| `payment_time` | DateTime(auto_now_add) | When payment was recorded |
| `status` | CharField(choices) | SUCCESS, FAILED |

**Constraints**: `chk_payment_method_valid`, `chk_payment_status_valid`

### 3.3 Seed Data (Migration 0002)

| Vehicle | Spot Size | Hourly Rate | Max Daily |
|---|---|---|---|
| MOTORCYCLE | COMPACT | $2.00 | $20.00 |
| MOTORCYCLE | REGULAR | $3.00 | $30.00 |
| MOTORCYCLE | OVERSIZED | $4.00 | $40.00 |
| CAR | REGULAR | $5.00 | $40.00 |
| CAR | OVERSIZED | $6.00 | $50.00 |
| TRUCK | OVERSIZED | $10.00 | $80.00 |

---

## 4. API Endpoints

### 4.1 POST `/api/v1/tickets/scan`

**Purpose**: Scans a ticket and calculates the dynamic fee.

**Request**:
```json
{ "ticket_code": "ABC123XYZ456" }
```

**Response** (200):
```json
{
  "ticket_id": 42,
  "ticket_code": "ABC123XYZ456",
  "vehicle_type": "CAR",
  "assigned_size": "REGULAR",
  "entry_time": "2026-03-28T09:00:00Z",
  "duration_hours": 26,
  "duration_days": 2,
  "hourly_rate": "5.00",
  "max_daily_rate": "40.00",
  "amount_owed": "80.00"
}
```

**Pricing Formula**:
```
duration_hours = ceil(elapsed_seconds / 3600)
num_days       = ceil(elapsed_seconds / 86400)
calculated_fee = duration_hours × hourly_rate
daily_cap      = max_daily_rate × num_days
final_fee      = min(calculated_fee, daily_cap)
```

**Error Responses**:
- 404: Ticket not found
- 400: Ticket not in OPEN status
- 500: No active pricing rule matches

### 4.2 POST `/api/v1/payments`

**Purpose**: Processes payment, closes ticket, releases spot.

**Request**:
```json
{
  "ticket_id": "ABC123XYZ456",
  "amount_paid": "40.00",
  "method": "CASH"
}
```

**Response** (201):
```json
{
  "message": "Payment successful. Exit gate opened.",
  "payment_id": 17,
  "amount_paid": "40.00",
  "ticket_code": "ABC123XYZ456",
  "exit_time": "2026-03-29T08:15:00Z"
}
```

**Server-side Validation**:
- Recalculates `amount_owed` independently (prevents client-side tampering)
- Rejects `amount_paid < amount_owed` with 400 + both values in response

**Error Responses**:
- 404: Ticket not found
- 400: Ticket not OPEN, or insufficient payment

---

## 5. Architecture Decisions

### 5.1 Multi-Day Pricing Cap

The `max_daily_rate` scales linearly with the number of calendar days parked:

```
2 hours parked  → 1 day  → cap = 1 × $40 = $40
26 hours parked → 2 days → cap = 2 × $40 = $80
```

This prevents a multi-day parker from being charged only a single day's max.

### 5.2 Server-Side Fee Recalculation at Payment Time

The payment endpoint does **not** trust the fee from the scan response. It recalculates using the same pricing formula at the moment of payment. This closes a gap where:
- Time passes between scan and payment (fee increases)
- A malicious client submits a fabricated `amount_paid`

### 5.3 OCC Release with Retry Loop

The exit flow mirrors the entry flow's OCC discipline:

```python
MAX_RELEASE_RETRIES = 3

for attempt in range(MAX_RELEASE_RETRIES):
    released = LotOccupancy.attempt_release(assigned_size)
    if released:
        break
    time.sleep(0.05)  # 50ms backoff

if not released:
    logger.warning(...)  # Alert — counter may be stale
```

This prevents a single CAS conflict from silently leaving the occupancy counter wrong. The payment still succeeds (ticket is PAID), but the warning log enables operational follow-up.

### 5.4 Django Admin Registration

`PricingRule` is registered with `list_editable` on `hourly_rate`, `max_daily_rate`, and `is_active` — allowing admins to adjust pricing directly from the list view without opening each record. `Payment` is read-only with `date_hierarchy` on `payment_time` for drill-down reporting.

---

## 6. Post-Review Fixes (2026-03-29)

Six issues were identified and patched in the review pass:

| # | Severity | Issue | Fix |
|---|---|---|---|
| 1 | 🔴 Bug | `max_daily_rate` capped at 1 day regardless of duration | Formula now uses `max_daily_rate × num_days` |
| 2 | 🔴 Bug | No underpayment validation — $0 accepted for a $40 ticket | Server recalculates fee and rejects `amount_paid < amount_owed` |
| 3 | 🟡 Code | Redundant `if request.user.is_authenticated` check | Removed — `IsAuthenticated` already enforces this |
| 4 | 🟡 Missing | `PricingRule` and `Payment` not in Django Admin | Registered with filters, search, editable fields |
| 5 | 🟡 Bug | Silent OCC release failure (CAS conflict swallowed) | Added 3-retry loop + `logger.warning` on failure |
| 6 | 🟢 Cleanup | Dead `processed_by` field in serializer | Removed — view uses `request.user` directly |

---

## 7. Verification

```bash
D:\Anaconda\python.exe manage.py check
# System check identified no issues (0 silenced).
```
