# Test Data Reference Sheet

This document lists the exact data populated in your database by the updated `generate_test_data` script. You can use this as a reference guide when performing manual API or UI testing.

## 1. User Accounts (IAM)
Use these credentials to test login, authentication, and Role-Based Access Control (RBAC).

| Username | Password | Role | Notes |
| :--- | :--- | :--- | :--- |
| `admin` | `admin123` | `ADMIN` (Superuser) | Has full access. Would normally require 2FA per PRD. |
| `attendant1` | `attendant123` | `ATTENDANT` | Restricted access. Used for scanning tickets & payments. |

## 2. Parking Spot Inventory
The physical parking spots available for allocation.

| Spot Size | Total Quantity | Spot Numbers (Identifiers) |
| :--- | :--- | :--- |
| **COMPACT** | 50 | `C-0001` through `C-0050` |
| **REGULAR** | 100 | `R-0051` through `R-0150` |
| **OVERSIZED** | 30 | `O-0151` through `O-0180` |

## 3. Active Tickets (Vehicles Currently Parked)
The script simulates a partially filled parking lot so you can immediately see data on the Occupancy Dashboard. **The `LotOccupancy` table has been automatically synced to reflect these totals.**

| Vehicle Type | Spot Reserved | Quantity | Simulating Entry Time |
| :--- | :--- | :--- | :--- |
| **MOTORCYCLE** | COMPACT | 15 parked | Entered between 0.5 to 5 hours ago |
| **CAR** | REGULAR | 40 parked | Entered between 0.5 to 5 hours ago |
| **TRUCK** | OVERSIZED | 10 parked | Entered between 0.5 to 5 hours ago |

*(Total Occupancy: 65 out of 180 spots)*

## 4. Historical Transactions (Payments & Revenue)
To ensure the Revenue Dashboard charts have data to display, the script populates historical payments for the last 7 days.

- **Transactions**: 10 randomized payments per day for the last 7 days (70 transactions total).
- **Amounts**: Randomized between $10.00 and $50.00.
- **Methods**: Randomly split across CASH, CREDIT, and MOBILE.
- **Tickets**: 70 matching historical `PAID` tickets.

## 5. Pricing Rules
These are the dynamic pricing matrices used when calculating exit fees based on vehicle type and spot size.

| Vehicle Type | Assigned Spot Size | Hourly Rate | Maximum Daily Rate |
| :--- | :--- | :--- | :--- |
| **MOTORCYCLE** | COMPACT | $5.00 | $25.00 |
| **MOTORCYCLE** | REGULAR | $5.00 | $25.00 |
| **MOTORCYCLE** | OVERSIZED | $5.00 | $25.00 |
| **CAR** | REGULAR | $10.00 | $50.00 |
| **CAR** | OVERSIZED | $12.00 | $60.00 |
| **TRUCK** | OVERSIZED | $20.00 | $100.00 |

> [!TIP]
> **Testing Overflow Logic**: You can test the overflow logic by filling up the `REGULAR` spots with cars. The 101st Car should automatically be assigned to an `OVERSIZED` spot based on the pricing matrix above and the `VEHICLE_SPOT_PRIORITY` defined in your models.
