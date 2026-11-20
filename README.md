# NEXUS — Distributed Order Processing & E-Commerce Platform

A production-grade, event-driven microservices backend engineered with **Python, Django, Django REST Framework, FastAPI, SQLAlchemy (Async), PostgreSQL, Redis, RabbitMQ, NGINX, Docker, Kubernetes, Prometheus, and Grafana**.

NEXUS is architected to solve real-world distributed systems challenges: **Database-per-Service isolation, Choreography-based Saga orchestration, Publisher Confirms, Dead-Letter Queues (DLX/DLQ), Redis Distributed Locking, Idempotent Payment Processing, and ORM/Cache performance optimization**.

---

## 1. System Architecture

~~~mermaid
flowchart TD
    Client([Client / Mobile / Web]) --> Gateway[NGINX API Gateway :8080\nRate Limiting & Reverse Proxy]

    Gateway -->|/api/v1/auth/*| Auth[Auth Service\nDjango + DRF :8001]
    Gateway -->|/api/v1/catalog/*| Product[Product & Inventory Service\nDjango + DRF :8002]
    Gateway -->|/api/v1/orders/*| Order[Order Processing Service\nDjango + DRF :8003]
    Gateway -->|/api/v1/payments/*| Payment[Payment Service\nFastAPI + Async SQLAlchemy :8004]

    Auth --> AuthDB[(PostgreSQL\nnexus_auth_db)]
    Product --> ProdDB[(PostgreSQL\nnexus_product_db)]
    Order --> OrderDB[(PostgreSQL\nnexus_order_db)]
    Payment --> PayDB[(PostgreSQL\nnexus_payment_db)]

    Auth & Product & Order & Payment --> Redis[(Redis 7\nCache / Distributed Lock / Deduplication)]

    Order -->|Publish: order.created| MQ[[RabbitMQ Topic Exchange\nnexus.events + nexus.dlx]]
    MQ -->|Consume & Reserve Stock| Product
    Product -->|Publish: inventory.reserved| MQ
    MQ -->|Consume & Charge Card| Payment
    Payment -->|Publish: payment.succeeded / failed| MQ
    MQ -->|Update Order State / Rollback Stock| Order & Product
    MQ -->|Consume & Send Email/SMS| Notif[Notification Worker\nPure Python + Pika + DLQ]
~~~

---

## 2. Microservices Breakdown & Engineering Highlights

| Service | Tech Stack | Dedicated Database | Key Engineering Patterns |
| :--- | :--- | :--- | :--- |
| **Auth Service** | Django 5 + DRF + SimpleJWT | `nexus_auth_db` + Redis DB 0 | Custom UUID `User` model, JWT Rotation & Blacklisting, Role-Based Access Control (`CUSTOMER` / `ADMIN`), Service-Layer architecture |
| **Product Service** | Django 5 + DRF + Pika | `nexus_product_db` + Redis DB 1 | **N+1 Query Elimination** (`select_related` + `prefetch_related`), Read-Through Redis Caching (`<15ms` hits), Row-level stock locking (`SELECT ... FOR UPDATE`) |
| **Order Service** | Django 5 + DRF + Pika | `nexus_order_db` + Redis DB 2 | Deterministic **Finite State Machine (FSM)**, **Redis Distributed Lock** (Lua atomic release), Immutable `OrderItem` Data Snapshotting |
| **Payment Service** | **FastAPI** + Async SQLAlchemy | `nexus_payment_db` + Redis DB 3 | **Idempotency-Key Engine** (zero double-charging), Async I/O (`asyncpg`), HMAC-SHA256 Webhook Signature Verification |
| **Notification Worker** | **Pure Python** + Pika + Redis | Stateless (Redis DB 4) | Protocol-based Dependency Injection, Manual `basic_ack`, Transient Requeue vs. Permanent **Dead-Letter Queue (DLQ)** routing |

---

## 3. Event-Driven Saga & RabbitMQ Reliability

All asynchronous inter-service communication flows through **RabbitMQ** (`nexus.events` Topic Exchange) with strict production reliability guarantees:
* **Publisher Confirms:** Every `EventProducer` enables `channel.confirm_delivery()` and publishes persistent messages (`delivery_mode=2`).
* **Dead-Letter Topology (`nexus.dlx`):** Every consumer declares its dedicated Dead-Letter Queue (`*.dlq`) before binding its main queue.
* **Transient vs. Permanent Failure Classification:**
  * `TransientProcessingError` (e.g., DB lock timeout or SMTP timeout): Requeued once (`basic_nack(requeue=True)`). If `method.redelivered` is `True`, rejected to the DLQ (`basic_reject(requeue=False)`) to prevent infinite poison-message loops.
  * `PermanentProcessingError` (e.g., malformed JSON or invalid schema): Immediately routed to the DLQ.
* **Consumer Idempotency:** Every event envelope carries a UUIDv4 `event_id`. Consumers deduplicate processed `event_id`s in Redis to achieve **Exactly-Once Processing** over **At-Least-Once Delivery**.

---

## 4. Performance Optimization & Caching Benchmarks

* **ORM Query Optimization (`product-service`):** Replaced naive nested serialization with composite database indexes, `select_related('category', 'brand')`, and `Prefetch('variants', queryset=ProductVariant.objects.select_related('inventory'))`, reducing catalog page queries from **40+ queries (~1,200 ms)** to **strictly 3 SQL queries (~35–50 ms)**—verified automatically via `django_assert_num_queries(3)` in Pytest.
* **Redis Read-Through Caching:** High-traffic product detail endpoints (`GET /api/v1/catalog/products/{slug}/`) serve cached responses in **under 15 ms** (`X-Cache: HIT`) with automatic cache invalidation on stock reservation or product updates.

---

## 5. Repository Structure

~~~text
nexus/
├── .github/workflows/ci-cd.yml     # GitHub Actions CI/CD Pipeline
├── docs/architecture/              # Mermaid Database ERDs & RabbitMQ Event Contracts
├── k8s/                            # Kubernetes Manifests (Deployments, StatefulSets, HPA, Ingress)
├── monitoring/                     # Prometheus Scrape Config & Grafana Dashboards
├── scripts/
│   ├── nginx/nginx.conf            # NGINX API Gateway & Rate Limiting
│   ├── postgres/init-multi-db.sql  # Multi-Database Initialization
│   └── rabbitmq/                   # Broker Config & Dead-Letter Policy Definitions
├── services/
│   ├── auth-service/               # Identity & JWT Microservice (Django/DRF)
│   ├── product-service/            # Catalog & Inventory Microservice (Django/DRF + Worker)
│   ├── order-service/              # Order State Machine & Saga Microservice (Django/DRF + Worker)
│   ├── payment-service/            # Async Payment Microservice (FastAPI + SQLAlchemy + Worker)
│   └── notification-service/       # Standalone RabbitMQ Notification Worker (Pure Python + Pika)
├── tests/
│   ├── e2e/                        # End-to-End Saga Integration Tests via API Gateway
│   └── performance/                # Locust High-Concurrency Load Testing Suite
├── docker-compose.yml              # Full Platform Local Orchestration
└── .env.example                    # Environment Configuration Template
~~~

---

## 6. Quickstart & Running Tests

### 1. Start the Complete Platform
~~~bash
cp .env.example .env
docker compose up -d --build
~~~

* **API Gateway:** `http://localhost:8080/health`
* **RabbitMQ Management UI:** `http://localhost:15672`
* **Prometheus UI:** `http://localhost:9090`
* **Grafana Dashboard:** `http://localhost:3000`

### 2. Run Automated Test Suites (Pytest)
~~~bash
docker compose exec auth-service pytest -v
docker compose exec product-service pytest -v
docker compose exec order-service pytest -v
docker compose exec payment-service pytest -v
docker compose exec notification-service pytest -v
~~~

### 3. Run End-to-End (E2E) & Load Tests (Locust)
~~~bash
pytest tests/e2e -v
locust -f tests/performance/locustfile.py --host=http://localhost:8080
~~~