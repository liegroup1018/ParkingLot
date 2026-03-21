# Parking Lot Management System - Product Requirements Document (PRD)

## 1. Executive Summary
The Parking Lot Management System is a centralized, online-only software solution designed to manage a large-scale parking facility of up to 10,000 spots. It governs multiple entry and exit gates, dynamic vehicle-to-space allocation, complex fee generation, and a comprehensive management dashboard for administrative oversight.

## 2. User Roles
* **Parking Attendants**: Operational staff stationed at exit gates responsible for scanning tickets, processing payments, and performing manual gate overrides when necessary.
* **Management Admins**: Back-office staff responsible for configuring pricing, managing space inventory, viewing real-time occupancy, extracting financial reports, and receiving system anomaly alerts.

## 3. Functional Requirements

### 3.1 Facility & Hardware Integration
* **Scale**: The system must support a total capacity of approximately 10,000 parking spots.
* **Gate Infrastructure**: Operate concurrently across 2 entrance gates and 2 exit gates.
* **Sensors**: Integrate with hardware (height sensors, inductive loops, and/or cameras) or allow attendant intervention at the entrance to classify vehicle types before issuing a ticket.

### 3.2 Vehicle & Spot Allocation
* **Categories**: Support three vehicle types (Motorcycles, Cars, Trucks) matched against three spot sizes (Compact, Regular, Oversized).
* **Overflow Logic**: If suitable spots for a vehicle type are full, the system permits parking in larger available spots.
* **Overflow Limits**: Administrators can configure an upper limit for this overflow behavior; once the limit is reached, entry is denied for that vehicle type.

### 3.3 Entry Flow & "Ticket-as-Reservation"
* **Reservation Model**: Upon pressing the entry button, the system verifies spot availability based on the classified vehicle type.
* **Ticket Issuance**: If available, the system decrements the inventory count and prints a physical ticket. This ticket acts as a guaranteed reservation token for a space. (Specific spot numbers are *not* assigned).
* **Full Capacity**: When the final ticket/reservation is issued for the lot's capacity, entry displays must show "FULL," and entrance gates must remain closed.

### 3.4 Exit Flow & Financial Processing
* **Fee Calculation**: Rates are dynamically calculated based on:
  1. The type of vehicle.
  2. The type of spot utilized.
  3. The time of day.
* **Maximum Daily Rate**: A hard daily cap applies to parking charges. No free grace periods are offered.
* **Payment Methods**: Attendants must be able to process both cash and digital (credit card/mobile) transactions.
* **Lost Tickets**: In the event of a lost physical ticket, the system defaults to charging the maximum daily rate. (Note: LPR integration is out of scope for the current iteration).

### 3.5 Admin Dashboard
* **Space Management**: CRUD (Create, Read, Update, Delete) operations for managing the layout and count of physical parking spaces.
* **Real-Time Monitoring**: Live visibility into lot occupancy and gate statuses.
* **Financial Reporting**: Access to historical and live revenue logs.
* **Rate Controls**: The ability to modify pricing structures on the fly.
* **Manual Overrides**: Admins and authorized attendants can trigger manual gate overrides safely from the dashboard.

## 4. Non-Functional Requirements (NFRs)

### 4.1 Reliability & Uptime
* **Strict "Online-Only" Mode**: To ensure financial and ticket tracking integrity, the system does not support an offline mode. If network connectivity is lost, all automated gate operations and ticket issuances must strictly pause until restored.

### 4.2 Security & Access
* **Role-Based Access Control (RBAC)**: Strict segregation of duties. Attendants only see payment and basic operational interfaces.
* **Two-Factor Authentication (2FA)**: Required for all Management Admin accounts.
* **Audit Logging**: Every sensitive action—including manual gate overrides, pricing rule changes, and space deletions—must be permanently logged and tied to the initiating user.

### 4.3 Monitoring & Alerting
* **Automated Notifications**: The system must proactively alert Management Admins via the dashboard (or external notification) under the following conditions:
  * Gate hardware or software malfunctions.
  * The parking lot reaching 95% overall capacity.
  * Anomalous parking durations (e.g., a ticket reservation active for 7+ days indicating an abandoned vehicle).
