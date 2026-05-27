# Track 11: Lost Ticket Handling Implementation

## Objective
Implement a solution for handling the "lost ticket" scenario, where an exiting vehicle cannot provide a physical ticket (and LPR is not available).

## Design & Engineering Decisions

1. **Surrogate Ticket Approach**
   - Without LPR, it is impossible to identify which `OPEN` ticket in the database corresponds to the vehicle at the exit gate.
   - To securely process the exit, release inventory, and calculate the fee, the system creates a *new* surrogate ticket directly marked with the `LOST` status.
   - The attendant provides the `vehicle_type` for the surrogate ticket.
   - The original physical ticket remains `OPEN` in the database and will eventually be flagged by the "abandoned vehicle" alert (tickets open for >7 days), allowing an Admin to void it.

2. **Pricing Default**
   - Per PRD §3.4, a lost ticket defaults to the maximum daily rate. 
   - `PricingService.calculate_fee` natively supports returning the `max_daily_rate` immediately if `ticket.status == TicketStatus.LOST`, simplifying our backend implementation.

3. **API-First & UI Integration**
   - Added `POST /api/v1/tickets/lost/` to accept a vehicle type and return a newly generated `ticket_code` and fee.
   - Created a dedicated `lost_ticket.html` interface so attendants can seamlessly select a vehicle type, view the max fee, and transition directly to the existing payment flow, reusing the robust `PaymentProcessView`.

## Files Modified
- `system_design.md`: Documented new use case and API.
- `apps/payments/serializers.py`: Added `LostTicketCreateSerializer`.
- `apps/payments/views.py`: Added `LostTicketCreateView`.
- `apps/payments/urls.py`: Routed the new view.
- `templates/attendant/scan_ticket.html`: Added link to lost ticket flow.
- `templates/attendant/lost_ticket.html`: Created dedicated UI.
- `apps/payments/tests.py`: Added comprehensive testing for the lost ticket flow.
