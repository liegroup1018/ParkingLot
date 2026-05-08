# Test Functional Coverage

This document summarizes the functionality covered by the test cases in:

- `apps/gates/tests.py`
- `apps/inventory/tests.py`
- `apps/payments/tests.py`

Each table includes the test class, test function, production code or endpoint under test, and the specific functionality covered.

## `apps/gates/tests.py`

### Ticket Model Tests

| Test Class | Test Function | Code Under Test | Functionality Covered |
|---|---|---|---|
| `TicketModelTest` | `test_code_auto_generated` | `Ticket` model | Verifies that `ticket_code` is automatically generated when a ticket is created. |
| `TicketModelTest` | `test_codes_are_unique_across_tickets` | `Ticket` model | Verifies generated ticket codes are unique across multiple tickets. |
| `TicketModelTest` | `test_default_status_is_open` | `Ticket.status`, `Ticket.is_open` | Verifies new tickets default to `OPEN` and `is_open` returns `True`. |
| `TicketModelTest` | `test_str_contains_code_and_type` | `Ticket.__str__()` | Verifies the string representation includes ticket code and vehicle type. |

### Entry Service Tests

| Test Class | Test Function | Code Under Test | Functionality Covered |
|---|---|---|---|
| `EntryServiceTest` | `test_happy_path_creates_ticket` | `EntryService.process_entry()` | Creates a valid entry ticket for an available spot. |
| `EntryServiceTest` | `test_reserves_occ_count` | `EntryService.process_entry()`, `LotOccupancy` | Verifies successful entry increments occupancy count and OCC version. |
| `EntryServiceTest` | `test_lot_full_raises_error` | `EntryService.process_entry()` | Raises `LotFullError` when no suitable spot is available. |
| `EntryServiceTest` | `test_motorcycle_overflow_to_regular` | `EntryService.process_entry()` | Allows motorcycle overflow from compact to regular spots. |
| `EntryServiceTest` | `test_motorcycle_overflow_to_oversized_when_regular_also_full` | `EntryService.process_entry()` | Allows motorcycle overflow to oversized spots when compact and regular spots are full. |
| `EntryServiceTest` | `test_truck_rejects_non_oversized` | `EntryService.process_entry()` | Rejects trucks when no oversized spots are available. |
| `EntryServiceTest` | `test_occ_conflict_raises_after_max_retries` | `EntryService.process_entry()` | Raises `OCCConflictError` after repeated optimistic concurrency failures. |
| `EntryServiceTest` | `test_retry_succeeds_on_second_attempt` | `EntryService.process_entry()` | Verifies OCC retry succeeds when the second reservation attempt works. |

### Override Service Tests

| Test Class | Test Function | Code Under Test | Functionality Covered |
|---|---|---|---|
| `OverrideServiceTest` | `test_creates_audit_log` | `OverrideService.process_override()` | Creates an audit log for a manual gate override. |
| `OverrideServiceTest` | `test_returns_summary_dict` | `OverrideService.process_override()` | Returns override summary data including gate ID, direction, and operator username. |
| `OverrideServiceTest` | `test_no_ticket_created` | `OverrideService.process_override()` | Confirms manual override does not create a parking ticket. |

### Gate Entry API Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `GateEntryAPITest` | `test_attendant_can_create_ticket` | `POST /api/v1/gates/entry/` | Allows authenticated attendants to create tickets. |
| `GateEntryAPITest` | `test_admin_can_create_ticket` | `POST /api/v1/gates/entry/` | Allows authenticated admins to create tickets. |
| `GateEntryAPITest` | `test_unauthenticated_returns_401` | `POST /api/v1/gates/entry/` | Rejects unauthenticated entry requests. |
| `GateEntryAPITest` | `test_lot_full_returns_409` | `POST /api/v1/gates/entry/` | Returns `409 Conflict` with code `LOT_FULL` when no spot is available. |
| `GateEntryAPITest` | `test_occ_conflict_returns_409` | `POST /api/v1/gates/entry/` | Returns `409 Conflict` with code `OCC_CONFLICT` when OCC reservation fails. |
| `GateEntryAPITest` | `test_invalid_vehicle_type_returns_400` | `POST /api/v1/gates/entry/` | Validates vehicle type input. |
| `GateEntryAPITest` | `test_missing_gate_id_returns_400` | `POST /api/v1/gates/entry/` | Validates required `gate_id`. |
| `GateEntryAPITest` | `test_occ_count_incremented_on_success` | `POST /api/v1/gates/entry/`, `LotOccupancy` | Confirms successful API entry increments occupancy count. |

### Gate Override API Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `GateOverrideAPITest` | `test_admin_override_returns_200` | `POST /api/v1/gates/{gate_id}/override/` | Allows admin users to trigger manual gate override. |
| `GateOverrideAPITest` | `test_attendant_cannot_override` | `POST /api/v1/gates/{gate_id}/override/` | Blocks attendants from manual override access. |
| `GateOverrideAPITest` | `test_audit_log_created` | `POST /api/v1/gates/{gate_id}/override/` | Confirms override API creates an audit log. |
| `GateOverrideAPITest` | `test_short_reason_returns_400` | `POST /api/v1/gates/{gate_id}/override/` | Validates minimum reason length. |
| `GateOverrideAPITest` | `test_invalid_direction_returns_400` | `POST /api/v1/gates/{gate_id}/override/` | Validates override direction. |
| `GateOverrideAPITest` | `test_no_ticket_created_on_override` | `POST /api/v1/gates/{gate_id}/override/` | Confirms override does not issue a ticket. |

### Ticket List API Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `TicketListAPITest` | `test_list_all_tickets` | `GET /api/v1/gates/tickets/` | Lists all tickets for authenticated users. |
| `TicketListAPITest` | `test_filter_by_status` | `GET /api/v1/gates/tickets/?status=OPEN` | Filters tickets by status. |
| `TicketListAPITest` | `test_filter_by_vehicle_type` | `GET /api/v1/gates/tickets/?vehicle_type=MOTORCYCLE` | Filters tickets by vehicle type. |
| `TicketListAPITest` | `test_unauthenticated_returns_401` | `GET /api/v1/gates/tickets/` | Rejects unauthenticated ticket list requests. |

### Ticket Detail API Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `TicketDetailAPITest` | `test_retrieve_by_code` | `GET /api/v1/gates/tickets/{ticket_code}/` | Retrieves a ticket by ticket code. |
| `TicketDetailAPITest` | `test_not_found_returns_404` | `GET /api/v1/gates/tickets/{ticket_code}/` | Returns `404 Not Found` for a nonexistent ticket code. |

## `apps/inventory/tests.py`

### Parking Spot Model Tests

| Test Class | Test Function | Code Under Test | Functionality Covered |
|---|---|---|---|
| `ParkingSpotModelTest` | `test_create_spot_defaults_active` | `ParkingSpot` model | New parking spots default to `ACTIVE`. |
| `ParkingSpotModelTest` | `test_spot_number_is_unique` | `ParkingSpot.spot_number` | Duplicate spot numbers are rejected by the database. |
| `ParkingSpotModelTest` | `test_str_representation` | `ParkingSpot.__str__()` | String output includes spot number and size type. |

### Lot Occupancy OCC Tests

| Test Class | Test Function | Code Under Test | Functionality Covered |
|---|---|---|---|
| `LotOccupancyOCCTest` | `test_reserve_success` | `InventoryService.attempt_reserve()` | Reserves available capacity and increments count/version. |
| `LotOccupancyOCCTest` | `test_reserve_fails_when_full` | `InventoryService.attempt_reserve()` | Reservation fails when the selected spot size is full. |
| `LotOccupancyOCCTest` | `test_reserve_increments_version` | `InventoryService.attempt_reserve()` | Multiple successful reserves increment OCC version. |
| `LotOccupancyOCCTest` | `test_reserve_third_attempt_fails` | `InventoryService.attempt_reserve()` | Reservation fails once capacity is exhausted. |
| `LotOccupancyOCCTest` | `test_reserve_nonexistent_size_returns_false` | `InventoryService.attempt_reserve()` | Unknown spot size returns `False`. |
| `LotOccupancyOCCTest` | `test_release_success` | `InventoryService.attempt_release()` | Releases a reserved spot and decrements count. |
| `LotOccupancyOCCTest` | `test_release_at_zero_returns_false` | `InventoryService.attempt_release()` | Release fails when occupancy is already zero. |
| `LotOccupancyOCCTest` | `test_available_size_motorcycle_prefers_compact` | `InventoryService.available_size_for_vehicle()` | Motorcycles prefer compact spots. |
| `LotOccupancyOCCTest` | `test_available_size_car_skips_compact` | `InventoryService.available_size_for_vehicle()` | Cars do not use compact spots. |
| `LotOccupancyOCCTest` | `test_available_size_falls_back_on_full_compact` | `InventoryService.available_size_for_vehicle()` | Returns no size when compact and fallback sizes are unavailable. |
| `LotOccupancyOCCTest` | `test_available_size_oversized_fallback` | `InventoryService.available_size_for_vehicle()` | Motorcycles can overflow to oversized spots. |
| `LotOccupancyOCCTest` | `test_truck_only_accepts_oversized` | `InventoryService.available_size_for_vehicle()` | Trucks only accept oversized capacity. |

### Spot CRUD API Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `SpotCRUDAPITest` | `test_admin_can_create_spot` | `POST /api/v1/spots/` | Admins can create parking spots. |
| `SpotCRUDAPITest` | `test_attendant_cannot_create_spot` | `POST /api/v1/spots/` | Attendants cannot create spots. |
| `SpotCRUDAPITest` | `test_unauthenticated_cannot_create` | `POST /api/v1/spots/` | Unauthenticated users cannot create spots. |
| `SpotCRUDAPITest` | `test_list_spots` | `GET /api/v1/spots/` | Authenticated users can list spots. |
| `SpotCRUDAPITest` | `test_filter_by_size_type` | `GET /api/v1/spots/?size_type=COMPACT` | Spots can be filtered by size type. |
| `SpotCRUDAPITest` | `test_admin_can_update_spot_status` | `PATCH /api/v1/spots/{id}/` | Admins can update spot status. |
| `SpotCRUDAPITest` | `test_attendant_cannot_update_spot` | `PATCH /api/v1/spots/{id}/` | Attendants cannot update spots. |
| `SpotCRUDAPITest` | `test_admin_can_delete_spot` | `DELETE /api/v1/spots/{id}/` | Admins can delete spots. |
| `SpotCRUDAPITest` | `test_duplicate_spot_number_returns_400` | `POST /api/v1/spots/` | Duplicate spot numbers return validation or conflict errors. |

### Bulk Seed API Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `BulkSeedAPITest` | `test_bulk_seed_creates_spots` | `POST /api/v1/spots/seed/` | Bulk seeding creates the requested number of spots. |
| `BulkSeedAPITest` | `test_bulk_seed_is_idempotent` | `POST /api/v1/spots/seed/` | Repeated seed calls append unique generated spots without conflicts. |
| `BulkSeedAPITest` | `test_bulk_seed_zero_all_returns_400` | `POST /api/v1/spots/seed/` | Rejects seed requests where all counts are zero. |
| `BulkSeedAPITest` | `test_attendant_cannot_seed` | `POST /api/v1/spots/seed/` | Attendants cannot bulk seed spots. |

### Summary and Occupancy API Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `SummaryAndOccupancyAPITest` | `test_summary_endpoint` | `GET /api/v1/spots/summary/` | Returns spot totals grouped by size/status. |
| `SummaryAndOccupancyAPITest` | `test_occupancy_endpoint` | `GET /api/v1/spots/occupancy/` | Returns occupancy rows with calculated availability. |
| `SummaryAndOccupancyAPITest` | `test_unauthenticated_cannot_see_occupancy` | `GET /api/v1/spots/occupancy/` | Requires authentication for occupancy data. |

### Management Command Tests

| Test Class | Test Function | Code Under Test | Functionality Covered |
|---|---|---|---|
| `InitLotOccupancyCommandTest` | `test_creates_rows_from_spots` | `init_lot_occupancy` command | Creates `LotOccupancy` rows from active parking spots. |
| `InitLotOccupancyCommandTest` | `test_resets_counts_by_default` | `init_lot_occupancy` command | Resets `current_count` and `version` by default. |
| `InitLotOccupancyCommandTest` | `test_keep_counts_flag_preserves_current_count_and_version` | `init_lot_occupancy --keep-counts` | Updates capacity while preserving live count/version. |
| `InitLotOccupancyCommandTest` | `test_excludes_maintenance_spots_from_capacity` | `init_lot_occupancy` command | Maintenance spots are excluded from capacity. |

## `apps/payments/tests.py`

Note: the workspace contains `apps/payments/tests.py`; `apps/payments/test.py` was not present.

### Pricing Service Tests

| Test Class | Test Function | Code Under Test | Functionality Covered |
|---|---|---|---|
| `PricingServiceTest` | `test_calculate_fee_under_daily_cap` | `PricingService.calculate_fee()` | Rounds partial hours up and calculates fee below the daily cap. |
| `PricingServiceTest` | `test_calculate_fee_hits_daily_cap` | `PricingService.calculate_fee()` | Applies `max_daily_rate` when hourly total exceeds the cap. |
| `PricingServiceTest` | `test_calculate_fee_multi_day` | `PricingService.calculate_fee()` | Applies multi-day daily-cap calculation. |
| `PricingServiceTest` | `test_missing_pricing_rule_raises_error` | `PricingService.calculate_fee()` | Raises `PricingError` when no active pricing rule exists. |

### Payment Service Tests

| Test Class | Test Function | Code Under Test | Functionality Covered |
|---|---|---|---|
| `PaymentServiceTest` | `test_process_payment_success` | `PaymentService.process_payment()` | Creates payment, marks ticket `PAID`, sets exit time, and releases occupancy. |
| `PaymentServiceTest` | `test_process_payment_insufficient_funds` | `PaymentService.process_payment()` | Raises `PaymentError` for underpayment. |

### Ticket Scan and Payment API Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `PaymentsAPITest` | `test_ticket_scan_success` | `POST /api/v1/tickets/scan/` | Scans an open ticket and returns fee/duration details. |
| `PaymentsAPITest` | `test_ticket_scan_not_found` | `POST /api/v1/tickets/scan/` | Unknown ticket code returns `404 Not Found`. |
| `PaymentsAPITest` | `test_payment_process_success` | `POST /api/v1/payments/` | Processes payment and marks ticket as `PAID`. |
| `PaymentsAPITest` | `test_payment_process_insufficient` | `POST /api/v1/payments/` | Rejects insufficient payment with `400 Bad Request`. |

### Admin Pricing and Reports Tests

| Test Class | Test Function | Endpoint / Code Under Test | Functionality Covered |
|---|---|---|---|
| `AdminPaymentsAPITest` | `test_attendant_cannot_update_pricing` | `PATCH /api/v1/pricing-rules/{id}/` | Attendants cannot update pricing rules. |
| `AdminPaymentsAPITest` | `test_admin_can_update_pricing` | `PricingRuleUpdateView`, `PATCH /api/v1/pricing-rules/{id}/` | Admins can update pricing and create a `PRICE_CHANGE` audit log. |
| `AdminPaymentsAPITest` | `test_revenue_report_access` | `RevenueReportView`, `GET /api/v1/reports/revenue/` | Revenue report is admin-only. |
| `AdminPaymentsAPITest` | `test_peak_hours_report_access` | `PeakHoursReportView`, `GET /api/v1/reports/peak-hours/` | Peak-hours report is admin-only. |

