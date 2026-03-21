# Parking Lot Management System - System Design

## 1. Core Modules and Use Cases

The Parking Lot Management System is logically divided into the following core modules. This modular approach ensures the system is scalable, maintainable, and allows different components to be developed or scaled independently.

### 1.1 Identity & Access Management (IAM) Module

*Handles security, authentication, and authorization for all human users.*

* **Use Case:** Admin logs in using Two-Factor Authentication (2FA).
* **Use Case:** Attendant logs in using standard credentials.
* **Use Case:** System verifies Role-Based Access Control (RBAC) permissions before allowing access to a specific endpoint.
* **Use Case:** System securely logs an audit trail for sensitive actions (e.g., manual gate override, pricing change).

### 1.2 Spot Inventory & Allocation Module

*The brain of the parking lot tracking real-time availability and capacity.*

* **Use Case:** System checks total availability for a specific vehicle type (Motorcycle, Car, Truck).
* **Use Case:** System applies "Overflow Logic" (e.g., allowing a car to park in an oversized spot up to a defined limit).
* **Use Case:** System temporarily reserves a spot and decrements inventory when a ticket is printed.
* **Use Case:** System restores spot inventory when a vehicle exits.
* **Use Case:** Admin creates, updates, or deletes physical parking spaces in the system.

### 1.3 Gate & Hardware Integration Module

*Manages the physical entry/exit points and interacts with hardware sensors.*

* **Use Case:** Hardware sensors (or attendant) classify the vehicle size at the entry gate.
* **Use Case:** System triggers the entry gate barrier to open after a ticket is issued.
* **Use Case:** System triggers the exit gate barrier to open after payment is successful.
* **Use Case:** Admin or authorized Attendant triggers a manual gate override from the dashboard.
* **Use Case:** System pauses all gate operations if the network/online connection drops.

### 1.4 Ticketing & Pricing Engine

*Manages the lifecycle of a ticket and dynamic fee calculations.*

* **Use Case:** System generates and issues a physical ticket containing an entry timestamp and vehicle class.
* **Use Case:** Attendant scans the ticket at the exit.
* **Use Case:** Pricing Engine calculates the fee based on dynamic rules (Vehicle Type + Spot Type + Time of Day).
* **Use Case:** System caps the calculated fee using the "Maximum Daily Rate" rule.
* **Use Case:** Admin dynamically configures or updates the pricing matrix/rules.

### 1.5 Payment Processing Module

*Handles the financial transaction at the exit.*

* **Use Case:** Attendant processes a cash payment and records it in the system.
* **Use Case:** System processes a digital payment (Credit Card / Mobile) via a third-party payment gateway.

### 1.6 Monitoring, Reporting & Alerting Module

*Provides back-office analytics and real-time operational health checks.*

* **Use Case:** Admin views real-time lot occupancy (e.g., 8,500 / 10,000 spots filled).
* **Use Case:** Admin exports historical revenue reports for a specific date range.
* **Use Case:** System automatically alerts Admins when the lot hits 95% capacity.
* **Use Case:** System scans for tickets older than 7 days and alerts Admins of a potentially abandoned vehicle.
* **Use Case:** System detects a hardware malfunction at a gate and triggers a critical alert.

## 2. database schema

**1. `Users` Table** (For IAM & RBAC)

* `user_id` (PK)
* `username`
* `password_hash`
* `role` (Enum: Admin, Attendant)
* `two_factor_secret`
* `created_at`, `updated_at`

**2. `ParkingSpots` Table** (Physical Inventory)

* `spot_id` (PK)
* `spot_number` (e.g., "A1", optional physical identifier)
* `size_type` (Enum: Compact, Regular, Oversized)
* `status` (Enum: Active, Maintenance)
* `created_at`, `updated_at`

**3. `Tickets` Table** (The core transaction/reservation token)

* `ticket_id` (PK)
* `ticket_code` (Unique literal printed on the ticket)
* `vehicle_type` (Enum: Motorcycle, Car, Truck)
* `assigned_spot_size` (The size of the spot they effectively "reserved")
* `entry_time`
* `exit_time` (Nullable, populated upon exit)
* `status` (Enum: Active, Paid, Lost)
* `fee_amount` (Nullable, final calculated fee)

**4. `PricingRules` Table** (Dynamic pricing configuration)

* `rule_id` (PK)
* `vehicle_type` (Enum)
* `spot_size` (Enum)
* `time_start` (e.g., 08:00)
* `time_end` (e.g., 18:00)
* `hourly_rate`
* `max_daily_rate`
* `is_active` (Boolean)

**5. `Payments` Table** (Financial Transactions)

* `payment_id` (PK)
* `ticket_id` (FK to Tickets)
* `processed_by` (FK to Users - Attendant)
* `amount`
* `payment_method` (Enum: Cash, Credit, Mobile)
* `payment_time`
* `status` (Enum: Success, Failed)

**6. `AuditLogs` Table** (Security & Monitoring)

* `log_id` (PK)
* `user_id` (FK to Users)
* `action_type` (e.g., "Manual Gate Open", "Price Change", "Spot Deleted")
* `details` (JSON payload of the change)
* `timestamp`

**7. `LotOccupancy` Table** (Fast Concurrency Control)

* `occupancy_id` (PK)
* `vehicle_type` / `spot_size` (To track specific counts)
* `total_capacity`
* `current_count`
* `version` (Used for Optimistic Concurrency Control)

## 3. api-design

### 1. Gate & Hardware APIs (Used by hardware controllers & sensors)

* `POST /api/v1/gates/entry`
  * **Payload:** `{ "gate_id": "ENT-1", "vehicle_type": "Car" }`
  * **Action:** Checks spot inventory. If space is available, decrements the spot count, opens the literal gate, and returns the newly generated ticket details payload. Returns a `409 Conflict` if the lot is FULL (or if the overflow limit for that vehicle type is reached).
* `POST /api/v1/gates/{gate_id}/override`
  * **Payload:** `{ "reason": "Emergency vehicle" }` (Requires authorization)
  * **Action:** Forces a mechanical gate open and commits a permanent event to the `AuditLogs` table with the user's ID.

### 2. Attendant / Exit APIs

* `POST /api/v1/tickets/scan`
  * **Payload:** `{ "ticket_code": "TKT-987654" }`
  * **Action:** Looks up the ticket, calculates the dynamic fee based on duration and vehicle size (capped at the daily maximum), and returns the amount owed to the attendant's screen.
* `POST /api/v1/payments`
  * **Payload:** `{ "ticket_id": "TKT-987654", "amount_paid": 25.00, "method": "Cash", "processed_by": "ATT-01" }`
  * **Action:** Records the transaction into the `Payments` table, updates the ticket status to `Paid`, restores the `ParkingSpots` inventory count, and automatically signals the exit gate to open.

### 3. Admin Dashboard APIs

* `GET /api/v1/lot/occupancy`
  * **Action:** Returns real-time remaining capacities categorized by spot sizes and vehicle classes (e.g., `returns { "regular_spots_available": 450, "compact_spots_available": 12 }`).
* `PUT /api/v1/pricing-rules/{rule_id}`
  * **Payload:** `{ "hourly_rate": 5.00, "max_daily_rate": 40.00 }`
  * **Action:** Dynamically updates a specific pricing matrix rule. Restricted to 2FA-authenticated Admins.
* `GET /api/v1/reports/revenue`
  * **Params:** `?start_date=2026-03-01&end_date=2026-03-10`
  * **Action:** Aggregates and returns revenue statistics generated from the `Payments` table.

## 4. Concurrency & Synchronization

To handle race conditions (e.g., two cars arriving at two different gates at the exact same millisecond when only 1 spot is left), we will use **Optimistic Concurrency Control (OCC)**.

Instead of locking rows or querying the entire `ParkingSpots` table on every entry, we maintain a `LotOccupancy` table with a `version` column.

**Entry Flow (OCC):**

1. Read the current occupancy and version: `SELECT current_count, version FROM LotOccupancy WHERE spot_size = 'Compact'`
2. Verify 'current_count' < 'total_capacity'.
3. Attempt to update: `UPDATE LotOccupancy SET current_count = current_count + 1, version = version + 1 WHERE spot_size = 'Compact' AND version = [read_version]`
4. If the update affects 0 rows, it means another gate processed a vehicle simultaneously. The transaction aborts and retries step 1.
5. If the update is successful, the system safely issues a ticket and opens the gate.

## 5. UI & Frontend Integration

The HTML interface is strictly designed as a separate track after the core backend APIs are established. This follows an **API-first methodology**, ensuring the database and business logic are rock solid before putting a face on them.

* **When to Design:** The UI development (Track 5) begins once the core Inventory, Gate, and Pricing APIs are complete.
* **How it Connects:** The Django backend will serve base HTML templates. These templates will include lightweight JavaScript (using `fetch()` or AJAX) to communicate synchronously with the Django REST Framework (DRF) APIs.
* **Interfaces:**
  * **Attendant Dashboard:** An HTML interface for staff to input ticket numbers, view dynamic pricing returned by `/api/v1/tickets/scan`, and submit payments to `/api/v1/payments`.
  * **Admin Dashboard:** We will leverage Django's powerful built-in `django.contrib.admin` for CRUD operations on users and spots, supplemented by custom charting views that pull from `/api/v1/reports/revenue`.
