# System Implementation Roadmap (Django + MySQL)

This roadmap breaks down the `system_design.md` into logical, sequential **Tracks** (development phases) for our Parking Lot Management System. Each track represents a testable, deployable unit of work that we will develop using Django and MySQL.

## Track 1: Foundation & Identity (`foundation-setup`) ✅ COMPLETE

*Goal: Initialize the Django project, set up the MySQL database, and establish core Identity & Access Management (IAM).*

- [x] **Task 1.1:** Initialize Django project and app structure.
- [x] **Task 1.2:** Configure `settings.py` to connect to the MySQL database.
- [x] **Task 1.3:** Create custom `User` model extending `AbstractUser` with specific `role` choices (Admin, Attendant).
- [x] **Task 1.4:** Generate initial Django database migrations and apply them (`python manage.py migrate`).
- [x] **Task 1.5:** Implement basic `AuditLogs` model to track sensitive system actions.
- [x] **Task 1.6:** Implement JWT Authentication (via `djangorestframework-simplejwt`) for the API endpoints.

## Track 2: Core Inventory (`core-inventory`)

*Goal: Build the physical parking spot representations and the fast concurrency tracker.*

- [x] **Task 2.1:** Create `ParkingSpots` model (spot_id, size_type, status).
- [x] **Task 2.2:** Create `LotOccupancy` model (for Optimistic Concurrency Control) with `current_count`, `total_capacity`, and `version`.
- [x] **Task 2.3:** Implement Admin API `POST /api/v1/spots` to seed the database with initial spot capacity.
- [x] **Task 2.4:** Write a Django management command to automatically initialize the `LotOccupancy` aggregate table based on `ParkingSpots` data.

## Track 3: Entry Gates & Hardware Integration (`gate-entry-flow`) ✅ COMPLETE

*Goal: Handle the incoming traffic, ticket generation, and high-concurrency race conditions (Strategy A).*

- [x] **Task 3.1:** Create `Tickets` model with entry constraints (vehicle_type, assigned_size, entry_time).
- [x] **Task 3.2:** Implement OCC logic inside `POST /api/v1/gates/entry`:
  - [x] Validate `vehicle_type` against remaining space in `LotOccupancy`.
  - [x] Use `F() expressions` or manual `version` CAS to safely decrement `current_count` and increment `version`.
  - [x] If successful, generate unique `ticket_code` and create `Tickets` record.
  - [x] Return 409 Conflict if OCC version mismatch occurs (prompting client retry) or lot is full.
- [x] **Task 3.3:** Implement `POST /api/v1/gates/{gate_id}/override` for manual openings. Write logs to `AuditLogs`.

## Track 4: Pricing Engine & Exit Flow (`pricing-exit-flow`)

*Goal: Process tickets leaving the lot, calculate dynamic rates, and free up inventory.*

- [ ] **Task 4.1:** Create `PricingRules` model (hourly, max_daily, vehicle/size modifiers) and `Payments` model.
- [ ] **Task 4.2:** Seed initial default `PricingRules` into the database.
- [ ] **Task 4.3:** Implement `POST /api/v1/tickets/scan`:
  - [ ] Look up `ticket_code`, fetch entry timestamp.
  - [ ] Query `PricingRules` and calculate fee dynamically (duration * rate, capped at max config).
  - [ ] Return calculated amount to Attendant client.
- [ ] **Task 4.4:** Implement `POST /api/v1/payments`:
  - [ ] Save payment record, validate amount, and update ticket status to `Paid`.
  - [ ] Restore inventory in `LotOccupancy` (OCC increment).
  - [ ] Signal Exit Gate API response.

## Track 5: Attendant UI & Frontend Integration (`frontend-ui`)

*Goal: Build the HTML/CSS and JavaScript interfaces for the Attendant screens, connecting directly to the backend DRF APIs.*

- [ ] **Task 5.1:** Set up base Django templates (`base.html`) and configure static assets (Tailwind CSS/Vanilla CSS).
- [ ] **Task 5.2:** Create the "Attendant Dashboard" view to display real-time lot occupancy.
- [ ] **Task 5.3:** Create the "Process Ticket" interface with a form to input ticket codes. Use JS `fetch()` to call `POST /api/v1/tickets/scan` and display the fee dynamically.
- [ ] **Task 5.4:** Create the checkout interface to submit payment data to `POST /api/v1/payments` and display the success/gate-open animation.

## Track 6: Admin Dashboard & Analytics (`admin-dashboard`)

*Goal: Provide real-time operational insights to management with a custom HTML/CSS responsive interface.*

- [ ] **Task 6.1:** Set up custom Admin HTML templates and CSS styling for the dashboard layout.
- [ ] **Task 6.2:** Implement `GET /api/v1/lot/occupancy` and render rapid snapshots on the Admin UI.
- [ ] **Task 6.3:** Implement `PUT /api/v1/pricing-rules/{rule_id}` and create a UI to allow Admins to change rates dynamically.
- [ ] **Task 6.4:** Implement `GET /api/v1/reports/revenue` aggregating records via SQL and display as frontend charts/tables.
- [ ] **Task 6.5:** Implement a background task (e.g., Celery or Django management cron) to scan for "abandoned" tickets (>7 days).
