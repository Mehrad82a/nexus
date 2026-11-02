# NEXUS — Event-Driven Architecture & RabbitMQ Contracts

All asynchronous communication across NEXUS microservices flows through **RabbitMQ** using a **Topic Exchange** (`nexus.events`).

## 1. Reliability & Production Standards
* **Exchange Type:** `topic` (`nexus.events`, `durable=True`)
* **Dead Letter Exchange (DLX):** `nexus.dlx` (`durable=True`) for failed messages after max retries.
* **Message Persistence:** `delivery_mode = 2` (Persistent).
* **Acknowledgments:** Manual `basic_ack` after successful database transaction commit.
* **Consumer Idempotency:** Every event envelope contains a unique `event_id` (UUIDv4). Consumers track processed `event_id`s in Redis/PostgreSQL to guarantee **Exactly-Once Processing** semantics over **At-Least-Once Delivery**.

---

## 2. Standard Event Envelope

Every message published to RabbitMQ must adhere to this strict JSON schema:

~~~json
{
  "event_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "event_type": "order.created",
  "timestamp": "2026-05-01T12:00:00Z",
  "source": "order-service",
  "version": "1.0",
  "payload": {}
}
~~~

---

## 3. Core Saga Workflow & Routing Keys

### Step 1: `order.created`
* **Publisher:** `order-service`
* **Routing Key:** `order.created`
* **Consumers:** `product-service` (Inventory Reservation)
* **Payload:**
~~~json
{
  "order_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "user_id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
  "total_amount": "1250.00",
  "currency": "USD",
  "items": [
    {
      "variant_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "quantity": 2
    }
  ]
}
~~~

### Step 2A: `inventory.reserved`
* **Publisher:** `product-service`
* **Routing Key:** `inventory.reserved`
* **Consumers:** `order-service` (updates status to `PAYMENT_PENDING`), `payment-service` (initiates payment)
* **Payload:**
~~~json
{
  "order_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "user_id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
  "total_amount": "1250.00",
  "currency": "USD",
  "reservation_id": "550e8400-e29b-41d4-a716-446655440000"
}
~~~

### Step 2B: `inventory.rejected` (Out of Stock Compensation)
* **Publisher:** `product-service`
* **Routing Key:** `inventory.rejected`
* **Consumers:** `order-service` (cancels order)
* **Payload:**
~~~json
{
  "order_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "reason": "INSUFFICIENT_STOCK",
  "failed_variant_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
}
~~~

### Step 3A: `payment.succeeded`
* **Publisher:** `payment-service`
* **Routing Key:** `payment.succeeded`
* **Consumers:** 
  * `order-service` (updates status to `PAID`)
  * `product-service` (permanently deducts reserved stock)
  * `notification-service` (sends confirmation email/SMS)
* **Payload:**
~~~json
{
  "payment_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "order_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "user_id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
  "amount": "1250.00",
  "provider_tx_id": "ch_3N2xYzMockStripe123"
}
~~~

### Step 3B: `payment.failed` (Saga Rollback / Compensation)
* **Publisher:** `payment-service`
* **Routing Key:** `payment.failed`
* **Consumers:**
  * `order-service` (updates status to `CANCELLED`)
  * `product-service` (releases reserved stock back to available inventory)
  * `notification-service` (sends payment failure alert)
* **Payload:**
~~~json
{
  "payment_id": "7c9e6679-7425-40de-944b-e07fc1f90ae7",
  "order_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "user_id": "1b9d6bcd-bbfd-4b2d-9b5d-ab8dfbbd4bed",
  "reason": "CARD_DECLINED"
}
~~~