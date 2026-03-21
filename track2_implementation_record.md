# Parking Lot — Implementation Record

## Track 1: Foundation & Identity ✅
*(Completed — see previous session)*

All IAM work done: custom User model, AuditLog, JWT login/refresh/logout,
RBAC permission classes, 2FA setup/verify, Django admin, full test suite.

---

## Track 2: Core Inventory ✅
**Completed: 2026-03-20**

### Files Created

```
apps/inventory/
├── __init__.py
├── apps.py                            AppConfig → InventoryConfig
├── models.py                          Task 2.1 ParkingSpot + Task 2.2 LotOccupancy
├── serializers.py                     CRUD + BulkSeed + OCC read + Summary
├── views.py                           Task 2.3 — all endpoints
├── urls.py                            Mounted at /api/v1/spots/
├── admin.py                           ParkingSpotAdmin + read-only LotOccupancyAdmin
├── tests.py                           42 test cases across model/API/command
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py               inventory_parking_spots + inventory_lot_occupancy
└── management/
    └── commands/
        └── init_lot_occupancy.py     Task 2.4 — management command
```

### Files Modified

| File | Change |
|------|--------|
| [config/settings.py](file:///e:/python%20project/ParkingLot/config/settings.py) | Added `apps.inventory.apps.InventoryConfig` to `LOCAL_APPS` |
| [config/urls.py](file:///e:/python%20project/ParkingLot/config/urls.py) | Mounted `apps.inventory.urls` at `/api/v1/spots/` |
| [ROADMAP.md](file:///e:/python%20project/ParkingLot/ROADMAP.md) | Ticked all Track 2 checkboxes |

---

### Task 2.1 — ParkingSpot Model

```
Table: inventory_parking_spots
```

| Field | Type | Notes |
|-------|------|-------|
| [id](file:///e:/python%20project/ParkingLot/apps/accounts/serializers.py#111-117) | BigAutoField PK | |
| [spot_number](file:///e:/python%20project/ParkingLot/apps/inventory/serializers.py#46-48) | CharField(20) UNIQUE | e.g. `COMPACT-0001` |
| [size_type](file:///e:/python%20project/ParkingLot/apps/inventory/tests.py#231-236) | CharField ENUM | COMPACT / REGULAR / OVERSIZED, `db_index=True` |
| [status](file:///e:/python%20project/ParkingLot/apps/inventory/tests.py#237-249) | CharField ENUM | ACTIVE / MAINTENANCE, `db_index=True` |
| `created_at` | DateTimeField | auto_now_add |
| `updated_at` | DateTimeField | auto_now |

**Indexes:**
- `idx_spots_size_status` — composite [(size_type, status)](file:///e:/python%20project/ParkingLot/apps/inventory/views.py#221-240) — the most common
  availability filter ("how many COMPACT ACTIVE spots?")

**DB Constraints (CHECK):**
- `chk_spot_size_type_valid` — size_type IN (COMPACT, REGULAR, OVERSIZED)
- `chk_spot_status_valid` — status IN (ACTIVE, MAINTENANCE)

---

### Task 2.2 — LotOccupancy Model (OCC sentinel)

```
Table: inventory_lot_occupancy
```

One row per [SpotSizeType](file:///e:/python%20project/ParkingLot/apps/inventory/models.py#33-38). Acts as the fast-path atomic counter.

| Field | Type | Notes |
|-------|------|-------|
| [id](file:///e:/python%20project/ParkingLot/apps/accounts/serializers.py#111-117) | BigAutoField PK | |
| `spot_size` | CharField UNIQUE | One row per size |
| `total_capacity` | PositiveIntegerField | Synced from active ParkingSpot count |
| [current_count](file:///e:/python%20project/ParkingLot/apps/inventory/tests.py#423-442) | PositiveIntegerField | Currently occupied |
| [version](file:///e:/python%20project/ParkingLot/apps/inventory/tests.py#116-123) | PositiveBigIntegerField | OCC CAS stamp |
| `updated_at` | DateTimeField | auto_now |

**OCC Pattern (entry gate — Track 3 will call these):**

```sql
-- 1. Read
SELECT spot_size, current_count, total_capacity, version
FROM inventory_lot_occupancy
WHERE spot_size = 'REGULAR';

-- 2. Guard (Python): current_count < total_capacity

-- 3. Atomic CAS update
UPDATE inventory_lot_occupancy
   SET current_count = current_count + 1,
       version       = version + 1
 WHERE spot_size       = 'REGULAR'
   AND version         = <read_version>          -- OCC check
   AND current_count   < total_capacity;          -- double-guard

-- 4. If rows_affected == 0 → conflict → retry step 1 (max 3 retries)
-- 5. If rows_affected == 1 → success → issue ticket
```

**OCC Class Methods on [LotOccupancy](file:///e:/python%20project/ParkingLot/apps/inventory/models.py#135-286):**

| Method | Description |
|--------|-------------|
| [attempt_reserve(spot_size)](file:///e:/python%20project/ParkingLot/apps/inventory/models.py#195-227) | Atomic increment (entry) — returns bool |
| [attempt_release(spot_size)](file:///e:/python%20project/ParkingLot/apps/inventory/models.py#228-254) | Atomic decrement (exit) — returns bool |
| [available_size_for_vehicle(vehicle_type)](file:///e:/python%20project/ParkingLot/apps/inventory/models.py#255-286) | Walks overflow priority list, returns first size with space |

**Overflow Priority (PRD §3.1):**

| Vehicle | Priority List |
|---------|---------------|
| Motorcycle | COMPACT → REGULAR → OVERSIZED |
| Car | REGULAR → OVERSIZED |
| Truck | OVERSIZED only |

---

### Task 2.3 — REST API Endpoints

| Method | Path | Access | Description |
|--------|------|--------|-------------|
| GET | `/api/v1/spots/` | Any auth | List all spots (filter: `?size_type=`, `?status=`) |
| POST | `/api/v1/spots/` | Admin | Create one spot |
| GET | `/api/v1/spots/<id>/` | Any auth | Retrieve spot detail |
| PATCH | `/api/v1/spots/<id>/` | Admin | Update status only (immutable after creation) |
| DELETE | `/api/v1/spots/<id>/` | Admin | Delete a spot |
| POST | `/api/v1/spots/seed/` | Admin | **Bulk seed** — auto-generate N spots per size |
| GET | `/api/v1/spots/summary/` | Any auth | Count by (size_type × status) |
| GET | `/api/v1/spots/occupancy/` | Any auth | OCC table snapshot (real-time dashboard) |

**Bulk seed body:**
```json
{
    "compact_count":   3000,
    "regular_count":   5000,
    "oversized_count": 2000
}
```
Auto-generates `COMPACT-0001 … COMPACT-3000` etc. Idempotent (re-runs append).

---

### Task 2.4 — Management Command

```bash
# Initialise from scratch (resets current_count and version to 0)
python manage.py init_lot_occupancy

# Resync capacity without disrupting live counts
python manage.py init_lot_occupancy --keep-counts
```

**What it does:**
1. `SELECT size_type, COUNT(*) FROM inventory_parking_spots WHERE status='ACTIVE' GROUP BY size_type`
2. `update_or_create` one [LotOccupancy](file:///e:/python%20project/ParkingLot/apps/inventory/models.py#135-286) row per size
3. Prints a summary table

> Run this every time you add/remove spots via the admin or seed endpoint.

---

### Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| [spot_number](file:///e:/python%20project/ParkingLot/apps/inventory/serializers.py#46-48) immutable | Only [status](file:///e:/python%20project/ParkingLot/apps/inventory/tests.py#237-249) is patchable | Spot identity must not change mid-lifecycle |
| OCC via [version](file:///e:/python%20project/ParkingLot/apps/inventory/tests.py#116-123) CAS | No DB-level lock (`SELECT FOR UPDATE`) | Lower latency at high concurrency; avoids lock escalation |
| `CheckConstraint` on DB | Both model-level and DB-level enum guards | Protects against bypassed ORM writes / raw SQL |
| `bulk_create(ignore_conflicts=True)` | Seed endpoint idempotent | Safe to re-run without duplicates |
| `--keep-counts` flag | On `init_lot_occupancy` | Allows live resync of `total_capacity` without resetting in-flight reservations |
| Overflow priority map | Defined as a module-level constant | Single source of truth shared between `LotOccupancy.available_size_for_vehicle()` and Track 3 gate views |

---

## Run Instructions

```bash
# Apply Track 2 migration
python manage.py migrate

# Seed 200 compact, 300 regular, 100 oversized spots
curl -X POST http://localhost:8000/api/v1/spots/seed/ \
  -H "Authorization: Bearer <ADMIN_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"compact_count": 200, "regular_count": 300, "oversized_count": 100}'

# Sync occupancy table
python manage.py init_lot_occupancy

# Verify occupancy
curl http://localhost:8000/api/v1/spots/occupancy/ \
  -H "Authorization: Bearer <TOKEN>"

# Run Track 2 tests
python manage.py test apps.inventory -v 2
```

---

## Next: Track 3 — Entry Gates & Hardware Integration

- Task 3.1: `Tickets` model
- Task 3.2: `POST /api/v1/gates/entry` — OCC reserve + ticket issuance
- Task 3.3: `POST /api/v1/gates/{gate_id}/override` — manual gate override + AuditLog
- Task 3.4: Retry logic (max 3 OCC retries, 409 on persistent failure)
