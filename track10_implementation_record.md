# Track 10 - Business Logic Service Layer Extraction

> **Status:** ✅ Complete  
> **Date:** 2026-05-07  
> **Validated:** `python manage.py test apps.inventory apps.payments apps.gates`

---

## 1. Motivation

Prior to this track, the system's core business logic for handling OCC (Optimistic Concurrency Control) and fee calculation/payment processing was embedded directly within the data models (`apps/inventory/models.py`) and API views (`apps/payments/views.py`). 

While this "Fat Model / Fat View" approach is acceptable for prototypes, it violates the separation of concerns for a system expected to scale up to 10,000 parking spots with strict transaction safety constraints. By extracting this logic into dedicated service classes, the codebase matches the existing pattern established in `apps/gates/services.py`, becoming significantly easier to test, maintain, and expand.

---

## 2. Files Changed

### `apps/inventory/`
- **[NEW] `services.py`**: Created `InventoryService` class. Moved the `attempt_reserve()`, `attempt_release()`, and `available_size_for_vehicle()` methods here.
- **`models.py`**: Removed the OCC helper class methods from `LotOccupancy`. Updated docstrings to point to the new service layer.
- **`tests.py`**: Updated all tests to mock and call `InventoryService` rather than `LotOccupancy`.

### `apps/payments/`
- **[NEW] `services.py`**: 
  - Created `PricingService.calculate_fee(ticket)` to encapsulate dynamic fee calculation.
  - Created `PaymentService.process_payment(ticket, amount_paid, method, user)` to handle transaction validation, ticket state updates, and trigger the spot release.
- **`views.py`**: Refactored `TicketScanView` and `PaymentProcessView` to consume the new `PricingService` and `PaymentService`.

### `apps/gates/`
- **`services.py`**: Updated `EntryService` OCC retry loops to call `InventoryService` methods instead of directly interacting with `LotOccupancy`.
- **`tests.py`**: Re-pointed `patch` decorators from `LotOccupancy` to `InventoryService` to fix failing mock assertions.

---

## 3. Behavioral Result

After this track:
1. The **external behavior and API schemas remain completely unchanged**. 
2. The business logic is now fully decoupled from the ORM models and HTTP request/response handling.
3. Views are now "Thin Views", solely responsible for input validation, calling a service method, and formatting the response.
4. Future tracks requiring pricing or inventory checks (e.g., custom admin overrides, or integrations) can reuse `InventoryService` and `PricingService` seamlessly without hacking view logic.

---

## 4. Migration Impact

- **No schema migration required.** These changes consist solely of code refactoring within the Python backend applications. No database fields were added, modified, or removed.

---

## 5. Verification

Executed tests across the modified applications to ensure logic integrity was preserved:

```bash
python manage.py test apps.inventory apps.payments apps.gates
```

Result:
- All unit tests pass successfully, confirming that the OCC retry logic, overflow capacity rules, and pricing calculation caps function identical to the previous implementation.
