# Lost Ticket Handling Implementation

This plan introduces a comprehensive solution for handling the "lost ticket" scenario. Since the system does not use LPR, the attendant cannot look up the original ticket code. To solve this, we will build a dedicated API and HTML interface that creates a surrogate "LOST" ticket. This allows the attendant to charge the maximum daily rate and trigger the exit gate while accurately tracking the lost ticket event.

## Proposed Changes

---

### 1. Documentation & System Design

#### [MODIFY] [system_design.md](file:///e:/python%20project/ParkingLot/system_design.md)
- Update the **Ticketing & Pricing Engine** and **Attendant / Exit APIs** sections to explicitly document the "Lost Ticket Surrogate Generation" use case.
- Clarify that a surrogate ticket will be generated to handle exit inventory release and billing.

#### [NEW] [track11_implementation_record.md](file:///e:/python%20project/ParkingLot/track11_implementation_record.md)
- Create a new track implementation record to document the engineering decisions and implementation details for the Lost Ticket feature.

---

### 2. Backend APIs (`apps/payments`)

We will introduce a new endpoint to generate a lost ticket, bypassing the need for a physical scan.

#### [MODIFY] [serializers.py](file:///e:/python%20project/ParkingLot/apps/payments/serializers.py)
- Add `LostTicketCreateSerializer` to accept and validate the `vehicle_type` from the attendant.

#### [MODIFY] [views.py](file:///e:/python%20project/ParkingLot/apps/payments/views.py)
- Add `LostTicketCreateView(APIView)` to handle `POST /api/v1/tickets/lost/`.
- The view will:
  1. Accept a `vehicle_type`.
  2. Determine the default `assigned_size` for that vehicle type (using `VEHICLE_SPOT_PRIORITY`).
  3. Create a new `Ticket` with `status=TicketStatus.LOST`.
  4. Call `PricingService.calculate_fee(ticket)` (which correctly defaults to `max_daily_rate` for `LOST` tickets).
  5. Return the newly generated `ticket_code` and fee details.
- This allows the frontend to immediately proceed to the existing `PaymentProcessView`.

#### [MODIFY] [urls.py](file:///e:/python%20project/ParkingLot/apps/payments/urls.py)
- Map `path("tickets/lost/", LostTicketCreateView.as_view(), name="ticket-lost")`.

---

### 3. Frontend HTML Interface (`templates/attendant`)

#### [NEW] [lost_ticket.html](file:///e:/python%20project/ParkingLot/templates/attendant/lost_ticket.html)
- A dedicated page allowing the attendant to select the `vehicle_type` for a lost ticket.
- Using AJAX, the form will hit `/api/v1/tickets/lost/` to generate the surrogate ticket and calculate the fee.
- The UI will display the maximum daily rate due and provide a "Proceed to Payment" button, similar to the `scan_ticket.html` flow.

#### [MODIFY] [scan_ticket.html](file:///e:/python%20project/ParkingLot/templates/attendant/scan_ticket.html)
- Add a "Lost Ticket?" button or link near the scan input that redirects the attendant to `lost_ticket.html`.

#### [MODIFY] [views.py](file:///e:/python%20project/ParkingLot/config/views.py) or relevant view
- Add a Django view to serve the `lost_ticket.html` template if needed.

## Verification Plan

### Automated Tests
- Create a test in `apps/payments/tests.py` to call `/api/v1/tickets/lost/` and verify that a ticket is created with `status=LOST` and returns the `max_daily_rate`.
- Verify that calling `/api/v1/payments/` with the generated lost ticket code successfully processes the payment, updates the status to `PAID`, and releases the correct inventory spot.

### Manual Verification
- Navigate to the Attendant interface, click the "Lost Ticket" button, select a vehicle type, and confirm that the surrogate ticket is created, the maximum fee is charged, and checkout completes successfully.
