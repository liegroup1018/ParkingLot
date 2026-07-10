# Database Entity-Relationship Diagram

This diagram maps out the relationships between all tables in the Parking Lot Management System, highlighting the Primary Keys (PK) and Foreign Keys (FK).

```mermaid
erDiagram
    %% Tables
    USER {
        bigint id PK
        varchar username
        varchar password
        varchar email
        varchar role
        varchar two_factor_secret
    }

    AUDIT_LOG {
        bigint id PK
        bigint user_id FK
        varchar action_type
        json details
        varchar ip_address
        datetime timestamp
    }

    TICKET {
        bigint id PK
        varchar ticket_code
        varchar vehicle_type
        varchar assigned_size
        varchar status
        datetime entry_time
        datetime exit_time
        bigint issued_by_id FK
    }

    PAYMENT {
        bigint id PK
        bigint ticket_id FK
        bigint processed_by_id FK
        decimal amount
        varchar payment_method
        datetime payment_time
        varchar status
    }

    PARKING_SPOT {
        bigint id PK
        varchar spot_number
        varchar size_type
        varchar status
        datetime created_at
        datetime updated_at
    }

    LOT_OCCUPANCY {
        bigint id PK
        varchar spot_size
        int total_capacity
        int current_count
        bigint version
        datetime updated_at
    }

    PRICING_RULE {
        bigint id PK
        varchar vehicle_type
        varchar spot_size
        time time_start
        time time_end
        decimal hourly_rate
        decimal max_daily_rate
        boolean is_active
    }

    %% Relationships
    USER ||--o{ AUDIT_LOG : "initiates (can be null for system)"
    USER ||--o{ TICKET : "issues (attendant)"
    USER ||--o{ PAYMENT : "processes (attendant)"
    TICKET ||--o| PAYMENT : "is settled by"
```

### Relationship Breakdown:
* **`USER` to `AUDIT_LOG` (1-to-Many):** One user can generate many audit logs. A log's foreign key (`user_id`) points to the User who initiated the action.
* **`USER` to `TICKET` (1-to-Many):** One user (an attendant) can issue many tickets.
* **`USER` to `PAYMENT` (1-to-Many):** One user (an attendant) can process multiple payments.
* **`TICKET` to `PAYMENT` (1-to-1/Many):** A ticket is settled by a payment. The payment holds the foreign key (`ticket_id`) linking back to the ticket. 

*(Note: `ParkingSpot`, `LotOccupancy`, and `PricingRule` do not have direct foreign key relationships in the database, as they are independently queried configuration or physical inventory tables.)*
