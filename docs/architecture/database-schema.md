# NEXUS — Database-per-Service Schema Design (ERD)

NEXUS strictly enforces the **Database-per-Service** pattern. Each microservice owns its logical database within PostgreSQL (`nexus_auth_db`, `nexus_product_db`, `nexus_order_db`, `nexus_payment_db`). 

Cross-service relationships use **UUID references** and **Data Snapshotting** rather than cross-database foreign keys, maintaining loose coupling and eventual consistency via RabbitMQ.

---

## 1. Auth Service Database (`nexus_auth_db`)

~~~mermaid
erDiagram
    USERS {
        uuid id PK
        string email UK
        string password_hash
        string first_name
        string last_name
        string role "CUSTOMER | ADMIN"
        boolean is_active
        boolean is_verified
        timestamp created_at
        timestamp updated_at
    }
~~~

---

## 2. Product & Inventory Service Database (`nexus_product_db`)

Designed specifically to demonstrate high-performance query optimization (`select_related`, `prefetch_related`, composite indexes, and Redis caching).

~~~mermaid
erDiagram
    CATEGORIES ||--o{ PRODUCTS : contains
    BRANDS ||--o{ PRODUCTS : manufactures
    PRODUCTS ||--o{ PRODUCT_VARIANTS : has
    PRODUCT_VARIANTS ||--|| INVENTORY : tracks
    INVENTORY ||--o{ INVENTORY_RESERVATIONS : locks

    CATEGORIES {
        uuid id PK
        string name
        string slug UK
        uuid parent_id FK "Nullable self-reference"
        boolean is_active
    }

    BRANDS {
        uuid id PK
        string name
        string slug UK
    }

    PRODUCTS {
        uuid id PK
        uuid category_id FK
        uuid brand_id FK
        string name
        string slug UK
        text description
        decimal base_price
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }

    PRODUCT_VARIANTS {
        uuid id PK
        uuid product_id FK
        string sku UK
        jsonb attributes "e.g., color, storage, size"
        decimal price_override "Nullable"
        boolean is_active
    }

    INVENTORY {
        uuid id PK
        uuid variant_id FK UK
        int total_quantity
        int reserved_quantity
        timestamp updated_at
    }

    INVENTORY_RESERVATIONS {
        uuid id PK
        uuid order_id UK "Idempotency reference"
        uuid variant_id FK
        int quantity
        string status "RESERVED | CONFIRMED | RELEASED"
        timestamp expires_at
        timestamp created_at
    }
~~~

---

## 3. Order Service Database (`nexus_order_db`)

Uses **Data Snapshotting** inside `ORDER_ITEMS` (`product_name`, `sku`, `unit_price`) so historical orders remain immutable even if product prices change later in `product-service`.

~~~mermaid
erDiagram
    ORDERS ||--|{ ORDER_ITEMS : contains
    ORDERS ||--o{ ORDER_STATUS_HISTORY : logs

    ORDERS {
        uuid id PK
        uuid user_id "Logical ref to Auth Service"
        string idempotency_key UK
        string status "PENDING | INVENTORY_RESERVED | PAYMENT_PENDING | PAID | SHIPPED | CANCELLED"
        decimal total_amount
        string currency
        jsonb shipping_address
        timestamp created_at
        timestamp updated_at
    }

    ORDER_ITEMS {
        uuid id PK
        uuid order_id FK
        uuid variant_id "Logical ref to Product Service"
        string product_name "Snapshot"
        string sku "Snapshot"
        int quantity
        decimal unit_price "Snapshot"
        decimal subtotal
    }

    ORDER_STATUS_HISTORY {
        uuid id PK
        uuid order_id FK
        string from_status
        string to_status
        string reason
        timestamp created_at
    }
~~~

---

## 4. Payment Service Database (`nexus_payment_db`)

Built with FastAPI and Async SQLAlchemy. Enforces strict **Idempotency** so duplicate requests or retried RabbitMQ messages never double-charge a customer.

~~~mermaid
erDiagram
    PAYMENTS {
        uuid id PK
        uuid order_id UK "Ensures 1 successful payment per order"
        uuid user_id
        string idempotency_key UK
        decimal amount
        string currency
        string provider "MOCK_STRIPE"
        string provider_tx_id
        string status "PENDING | SUCCEEDED | FAILED | REFUNDED"
        string failure_reason
        timestamp created_at
        timestamp updated_at
    }
~~~