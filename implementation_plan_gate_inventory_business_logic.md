# Business Logic Extraction to Service Layer

The current architecture has embedded core business logic directly within models (`apps/inventory/models.py` uses class methods on `LotOccupancy` for Optimistic Concurrency Control) and views (`apps/payments/views.py` calculates fees and processes payments directly). 

**Is this approach appropriate?** 
No. While acceptable for a prototype, this "Fat Model / Fat View" approach is not appropriate for a system designed to manage up to 10,000 spots with strict OCC (Optimistic Concurrency Control) requirements and financial auditing. Co-locating this logic makes the system harder to test in isolation, reduces reusability, and bloats the presentation (views) and data access (models) layers. Extracting this logic into dedicated service classes (which `apps/gates/` already demonstrates) will standardize the architecture and adhere to separation of concerns.

This plan details the remediation steps to extract these responsibilities into new `services.py` modules.

## User Review Required

> [!NOTE]
> The current system uses class methods directly on the `LotOccupancy` model (`attempt_reserve`, `attempt_release`, `available_size_for_vehicle`). These will be moved to `InventoryService` in `apps/inventory/services.py`. Calls to these methods in `apps/gates/services.py` and `apps/payments/views.py` will be updated to point to the new service layer.

## Open Questions

> [!TIP]
> Are there any specific error handling or logging standards you'd like added to the new service classes beyond what's currently in the views? The current plan assumes we will migrate the existing logs verbatim.

## Proposed Changes

### Inventory Component
Extracting OCC and spot availability logic from models to a service class.

#### [NEW] [services.py](file:///e:/python%20project/ParkingLot/apps/inventory/services.py)
- Create `InventoryService` class.
- Move `attempt_reserve`, `attempt_release`, and `available_size_for_vehicle` logic from `LotOccupancy` model here.

#### [MODIFY] [models.py](file:///e:/python%20project/ParkingLot/apps/inventory/models.py)
- Remove `attempt_reserve`, `attempt_release`, and `available_size_for_vehicle` from `LotOccupancy`.

---

### Payments Component
Extracting fee calculation and payment processing from the views to service classes.

#### [NEW] [services.py](file:///e:/python%20project/ParkingLot/apps/payments/services.py)
- Create `PricingService` class with a `calculate_fee(ticket)` method.
- Create `PaymentService` class with a `process_payment(ticket, amount_paid, method, user)` method.

#### [MODIFY] [views.py](file:///e:/python%20project/ParkingLot/apps/payments/views.py)
- Update `TicketScanView` to rely on `PricingService.calculate_fee()`.
- Update `PaymentProcessView` to rely on `PaymentService.process_payment()`.

---

### Gates Component (Dependency Update)
Update dependent components to use the new `InventoryService`.

#### [MODIFY] [services.py](file:///e:/python%20project/ParkingLot/apps/gates/services.py)
- Update `EntryService` to call `InventoryService.available_size_for_vehicle()` and `InventoryService.attempt_reserve()` instead of `LotOccupancy`.

---

### Documentation
Document the change using the project's track-management pattern.

#### [NEW] [track10_implementation_record.md](file:///e:/python%20project/ParkingLot/track10_implementation_record.md)
- Create a standard implementation record documenting the refactoring of the service layer.

## Verification Plan

### Automated Tests
- Run `python manage.py check` to ensure no syntax or basic configuration errors.
- Run `python manage.py test` to verify that existing test suites pass.

### Manual Verification
- Code review of the refactored code to ensure business logic is properly encapsulated in service classes and no logic remains directly inside the views or models.
