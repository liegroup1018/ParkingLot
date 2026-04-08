# Architectural Pattern Recognition: Parking Lot Management System

Based on the provided `prd.md` and `system_design.md` documents, the system architecture can be recognized as a **Modular Monolith** employing an **API-First Client-Server** pattern with **Optimistic Concurrency Control (OCC)** for data integrity.

## 1. Identified Architectural Patterns

1. **Modular Monolith**: The backend is logically divided into self-contained core modules (IAM, Spot Inventory, Gate & Hardware, Ticketing & Pricing, Payment, and Monitoring). They share a single relational database but maintain distinct boundaries, ensuring separation of concerns while keeping operations within a single application scope for simplicity and ease of deployment.
2. **API-First (Backend-for-Frontend)**: The Django backend acts as an API provider (via Django REST Framework) serving structured JSON payloads. The UI relies on lightweight decoupled asynchronous JavaScript (AJAX/Fetch) polling against these REST APIs, shifting from the traditional Django MTV (Model-Template-View) pattern into a more modern SPA-like interactive interface.
3. **Optimistic Concurrency Control (OCC)**: Built directly into the data tier (specifically the `LotOccupancy` table) to safely and efficiently process rapid, concurrent hardware events (such as multiple cars arriving at gates simultaneously) without aggressive database locking, minimizing race conditions natively.

## 2. System Architecture (Container Diagram)

```mermaid
graph TD
    subgraph Clients
        AD[Admin Dashboard<br/>HTML/CSS/JS]
        ATT[Attendant Dashboard<br/>HTML/CSS/JS]
        GATE[Gate Hardware Sensors]
    end

    subgraph Backend Server - Django
        API[DRF API Layer]
        
        subgraph Core Modules
            IAM[Identity & Access Management]
            INVENTORY[Spot Inventory & Allocation]
            GATE_MOD[Gate & Hardware Integration]
            PRICING[Ticketing & Pricing Engine]
            PAYMENT[Payment Processing]
            MONITOR[Monitoring & Reporting]
        end
        
        API --> IAM
        API --> INVENTORY
        API --> GATE_MOD
        API --> PRICING
        API --> PAYMENT
        API --> MONITOR
    end

    subgraph Database Layer
        RDBMS[(Relational Database<br/>OCC Enabled)]
    end

    AD -- AJAX/Fetch --> API
    ATT -- AJAX/Fetch --> API
    GATE -- HTTP/REST --> API
    
    IAM --> RDBMS
    INVENTORY --> RDBMS
    GATE_MOD --> RDBMS
    PRICING --> RDBMS
    PAYMENT --> RDBMS
    MONITOR --> RDBMS
```

## 3. Core Module Interactions & OCC Flow

This diagram showcases the optimistic concurrency flow during a spot logic check, reinforcing the scalable transactional patterns utilized by the inventory module.

```mermaid
sequenceDiagram
    participant Hardware as Gate Sensor
    participant GateMod as Gate Module
    participant InvMod as Inventory Module
    participant DB as LotOccupancy DB
    participant TicketMod as Ticketing Module

    Hardware->>GateMod: POST /api/v1/gates/entry (Vehicle Type)
    GateMod->>InvMod: Check Availability
    InvMod->>DB: Read current_count, version (OCC)
    DB-->>InvMod: Returns count, version
    InvMod->>DB: UPDATE LotOccupancy SET count+1, version+1 WHERE version=old_version
    
    alt OCC Conflict
        DB-->>InvMod: Update Failed (0 rows)
        InvMod-->>GateMod: Return Conflict / Retry logic
    else OCC Success
        DB-->>InvMod: Update Success
        InvMod->>TicketMod: Reserve Spot & Issue Ticket
        TicketMod-->>GateMod: Return Ticket Payload
        GateMod-->>Hardware: Open Gate & Print Ticket
    end
```

## 4. Database Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    Users ||--o{ AuditLogs : "generates"
    Users ||--o{ Payments : "processes"
    Tickets ||--o{ Payments : "has"
    PricingRules {
        int rule_id PK
        string vehicle_type
        string spot_size
        time time_start
        time time_end
        float hourly_rate
        float max_daily_rate
        boolean is_active
    }
    ParkingSpots {
        int spot_id PK
        string spot_number
        string size_type
        string status
    }
    Tickets {
        int ticket_id PK
        string ticket_code
        string vehicle_type
        string assigned_spot_size
        datetime entry_time
        datetime exit_time
        string status
        float fee_amount
    }
    Payments {
        int payment_id PK
        int ticket_id FK
        int processed_by FK
        float amount
        string payment_method
        datetime payment_time
        string status
    }
    Users {
        int user_id PK
        string username
        string password_hash
        string role
        string two_factor_secret
    }
    AuditLogs {
        int log_id PK
        int user_id FK
        string action_type
        json details
        datetime timestamp
    }
    LotOccupancy {
        int occupancy_id PK
        string vehicle_type
        int total_capacity
        int current_count
        int version
    }
```
