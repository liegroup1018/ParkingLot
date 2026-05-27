# Playwright Browser Testing Implementation Plan

This plan addresses the requirement to include HTML interaction tests for all new features using Playwright, specifically applying it to the newly created `lost_ticket.html` feature.

## User Review Required

> [!IMPORTANT]
> The system design documentation will be updated to mandate browser-level interaction tests (Playwright) for all new HTML features.
>
> A new Playwright test will be added to simulate the attendant selecting a vehicle type, generating a lost ticket, and transitioning to checkout. 
> 
> Please review the test flow below and let me know if you approve.

## Proposed Changes

---

### 1. System Documentation Update

#### [MODIFY] [system_design.md](file:///e:/python%20project/ParkingLot/system_design.md)
- Add a new sub-section under **5. UI & Frontend Integration** detailing the HTML interaction testing strategy.
- Explicitly state that all new HTML pages or interactive flows MUST be accompanied by browser-level tests using the Playwright framework.

### 2. Browser Tests

#### [MODIFY] [tests_html_interaction.py](file:///e:/python%20project/ParkingLot/apps/payments/tests_html_interaction.py)
- Introduce a new test method `test_generate_lost_ticket_flow` inside the `PaymentsHtmlInteractionTests` suite.
- **Test Steps**:
  1. Authenticate the attendant via the `seed_auth()` helper.
  2. Navigate directly to `/attendant/app/lost/`.
  3. Select a vehicle type (e.g., `CAR`) from the dropdown.
  4. Submit the form to generate the surrogate ticket.
  5. Wait for the `#fee-result` container to become visible.
  6. Assert that the `#fee-amount` reflects the maximum daily rate (`CNY 50.00`).
  7. Click "Proceed to Payment" and verify the browser navigates to `/attendant/app/checkout/`.
  8. Verify that the session storage correctly holds the generated `pending_ticket` and populates the checkout page fields.

## Verification Plan

### Automated Tests
- Run the `apps/payments/tests_html_interaction.py` suite via `python manage.py test`.
- Ensure all previously passing Playwright tests continue to pass and the new `test_generate_lost_ticket_flow` succeeds.
