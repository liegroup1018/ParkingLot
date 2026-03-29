# Track 6: Admin Dashboard & Analytics

This plan outlines the steps and architecture for implementing the Admin Dashboard & Analytics features (Track 6 of the Roadmap) to provide real-time operational insights for management.

## Proposed Changes

We will distribute the URLs across our existing applications instead of creating a brand new app, to maintain high cohesion:

### 1. Lot Occupancy API (`apps/inventory`)
To fulfill `GET /api/v1/lot/occupancy`:
#### [NEW] `apps/inventory/views.py` (Add missing views or functions)
- Create `LotOccupancyView` (GET) to query and serialize all `LotOccupancy` rows. This will return a rapid snapshot of current capacity and availability.

#### [MODIFY] `apps/inventory/urls.py`
- Route `occupancy/` to `LotOccupancyView`. (This will be under `/api/v1/spots/occupancy/` or we can map `/api/v1/lot/occupancy/` directly in `config/urls.py`).

### 2. Pricing Rules Update API (`apps/payments`)
To fulfill `PUT /api/v1/pricing-rules/{rule_id}`:
#### [MODIFY] `apps/payments/views.py`
- Add `PricingRuleUpdateView` extending `UpdateAPIView` to allow administrators (using `IsAdminRole` permission) to update existing pricing rules (e.g. modify `hourly_rate`, `max_daily_rate`).
#### [MODIFY] `apps/payments/serializers.py`
- Add `PricingRuleUpdateSerializer` limiting which fields can be edited.
#### [MODIFY] `apps/payments/urls.py`
- Add routing for the new pricing rules endpoint.

### 3. Revenue Reports API (`apps/payments`)
To fulfill `GET /api/v1/reports/revenue`:
#### [MODIFY] `apps/payments/views.py`
- Add `RevenueReportView` (GET), accessible only to Admins. It will use Django's ORM `TruncDate` and `Sum` functions to aggregate data from the `Payment` table grouped by day (optionally filtered by a date range).
#### [MODIFY] `config/urls.py`
- We will add standard routing for `/api/v1/reports/revenue/` and `/api/v1/lot/occupancy/` (if we choose not to nest them under `spots` or `payments`).

### 4. Abandoned Tickets Scanner (`apps/gates`)
To fulfill the background task scanning for "abandoned" tickets (>7 days):
#### [NEW] `apps/gates/management/commands/scan_abandoned.py`
- Create a custom Django management command that scans for `Ticket` records where `status=OPEN` and `entry_time` is older than 7 days.
- Uses the already provided `(status, entry_time)` composite index naturally.
- The command can log warnings, alert, or flag the tickets automatically.

## Verification Plan

### Automated / Manual Testing
- **Lot Occupancy**: Request endpoint and verify response totals match db state minus occupied slots.
- **Pricing Rule Updates**: Use Admin credentials to PUT a change to a rule, ensure changes reflect in DB and affect subsequent ticket scans. Verify Attendants get HTTP 403 on this endpoint.
- **Revenue Report**: Make payments via previously implemented payment endpoints, then request the revenue report and assert correct mathematical aggregations by date.
- **Abandoned Tasks**: Insert a dummy ticket backdated >7 days via Django shell and run `python manage.py scan_abandoned`. Ensure it correctly flags the older ticket and ignores newer open tickets.
