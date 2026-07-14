# Database Schema - Data Dictionary

This document explains the meaning and purpose of every field across all tables in the Parking Lot Management System database.

## 1. `LotOccupancy` Table (Inventory App)
*This is where the upper limits (capacities) for the spot types are set and tracked.*
数据库中的表名：inventory_lot_occupancy

- **`spot_size`**: The category of the parking spot (`COMPACT`, `REGULAR`, `OVERSIZED`).
- **`total_capacity`**: **The upper limit for this spot type.** It represents the total number of physical spots that exist in the facility for this size.
- **`current_count`**: The number of vehicles currently occupying this spot size.
- **`version`**: Used for Optimistic Concurrency Control (OCC) to prevent race conditions when two cars arrive at different gates simultaneously.
- **`updated_at`**: Timestamp of the last time a vehicle entered or exited.

## 2. `ParkingSpot` Table (Inventory App)
*Represents the literal, physical parking spaces on the pavement.*
数据库中的表名：inventory_parking_spots

- **`spot_number`**: A human-readable identifier (e.g., "C-0001" for a compact spot).
- **`size_type`**: The size of the spot (`COMPACT`, `REGULAR`, `OVERSIZED`).
- **`status`**: Whether the spot is `ACTIVE` or down for `MAINTENANCE`.
- **`created_at` / `updated_at`**: Timestamps for when the spot record was created or modified.

## 3. `User` Table (Accounts App)
*Handles staff authentication and authorization.*
数据库中的表名：accounts_users

- **`username` / `password` / `email`**: Standard login credentials.
- **`role`**: The Role-Based Access Control (RBAC) level (`ADMIN`, `ATTENDANT`, `SUPERUSER`). Determines what UI dashboards and API endpoints the user can access.
- **`two_factor_secret`**: The Time-based One-Time Password (TOTP) secret used for 2FA (required for Admins).
- **`is_active` / `is_staff` / `is_superuser`**: Django's internal flags for account status and admin panel access.

## 4. `AuditLog` Table (Accounts App)
*Immutable ledger of sensitive actions (security & compliance).*
数据库中表名：accounts_audit_logs

- **`user_id`**: The staff member who performed the action (can be null if system-generated).
- **`action_type`**: The semantic category of the action (e.g., `MANUAL_GATE_OPEN`, `PRICE_CHANGE`, `USER_CREATED`).
- **`details`**: A JSON payload containing the specific changes made (e.g., the old price vs the new price).
- **`ip_address`**: The network IP address of the user making the request.
- **`timestamp`**: The exact UTC time the action occurred.

## 5. `Ticket` Table (Gates App)
*The core transactional record of a vehicle's stay in the parking lot.*
数据库中表名：gates_tickets

- **`ticket_code`**: A unique 12-character alphanumeric code printed on the physical ticket stub.
- **`vehicle_type`**: The actual type of the vehicle (`MOTORCYCLE`, `CAR`, `TRUCK`).
- **`assigned_size`**: The size of the spot they were assigned. *(Note: Due to overflow logic, a Car might be assigned an OVERSIZED spot if all REGULAR spots are full).*
- **`status`**: The current state of the ticket (`OPEN`, `PAID`, `LOST`, `VOIDED`).
- **`entry_time`**: When the vehicle entered. The pricing clock starts here.
- **`exit_time`**: When the vehicle successfully paid and left the lot.
- **`issued_by_id`**: The attendant or automated gate system account that generated the ticket.

## 6. `PricingRule` Table (Payments App)
*The dynamic configuration that determines how much a ticket costs.*
数据库中表名：payments_pricing_rules

- **`vehicle_type`**: The class of the vehicle.
- **`spot_size`**: The size of the spot they parked in.
- **`time_start` / `time_end`**: The time window (e.g., 08:00 to 18:00) during which this specific rate applies.
- **`hourly_rate`**: The amount charged per hour of stay.
- **`max_daily_rate`**: The absolute maximum a vehicle can be charged for a 24-hour period, regardless of the hourly accumulation.
- **`is_active`**: A toggle to turn a pricing rule on or off without deleting it.

## 7. `Payment` Table (Payments App)
*The financial ledger of settled transactions.*
数据库中表名：payments_transactions

- **`ticket_id`**: A link to the Ticket this payment settled.
- **`processed_by_id`**: The attendant who collected the payment (if manual).
- **`amount`**: The final monetary value charged and collected.
- **`payment_method`**: How the customer paid (`CASH`, `CREDIT`, `MOBILE`).
- **`payment_time`**: The exact time the transaction was processed.
- **`status`**: Whether the payment was a `SUCCESS` or `FAILED`.
