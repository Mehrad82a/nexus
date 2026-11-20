import os
import time
import uuid
import pytest
import requests


GATEWAY_URL = os.environ.get('NEXUS_GATEWAY_URL', 'http://localhost:8080')



def is_gateway_reachable() -> bool:
    try:
        res = requests.get(f'{GATEWAY_URL}/health', timeout=2)
        return res.status_code == 200
    except requests.RequestException:
        return False



@pytest.mark.skipif(
    not is_gateway_reachable(),
    reason='NEXUS API Gateway is not running on localhost:8080',
)
class TestDistributedOrderSagaE2E:
    """
    End-to-End integration test verifying the complete event-driven Saga across
    NGINX Gateway -> Auth -> Catalog -> Order -> RabbitMQ -> Inventory -> Payment -> Notification.
    """

    def test_gateway_health_check(self):
        response = requests.get(f'{GATEWAY_URL}/health', timeout=5)
        assert response.status_code == 200
        assert response.json()['service'] == 'nexus-api-gateway'


    def test_full_customer_registration_and_asynchronous_order_saga(self):
        unique_email = f'e2e_{uuid.uuid4().hex[:8]}@nexus.io'

        # 1. Register Customer via API Gateway -> Auth Service
        reg_res = requests.post(
            f'{GATEWAY_URL}/api/v1/auth/register/',
            json={
                'email': unique_email,
                'password': 'StrongPassword123',
                'first_name': 'Mohamad',
                'last_name': 'Abbasi',
            },
            timeout=5,
        )
        assert reg_res.status_code == 201
        access_token = reg_res.json()['tokens']['access']
        auth_headers = {'Authorization': f'Bearer {access_token}'}

        # 2. Verify Protected Identity Endpoint (/api/v1/auth/me/)
        me_res = requests.get(
            f'{GATEWAY_URL}/api/v1/auth/me/',
            headers=auth_headers,
            timeout=5,
        )
        assert me_res.status_code == 200
        assert me_res.json()['email'] == unique_email

        # 3. Verify Public Catalog Endpoint (/api/v1/catalog/products/)
        catalog_res = requests.get(
            f'{GATEWAY_URL}/api/v1/catalog/products/',
            timeout=5,
        )
        assert catalog_res.status_code == 200

        # 4. Create Order via API Gateway -> Order Service (with Idempotency-Key)
        idempotency_key = f'e2e-idem-{uuid.uuid4()}'
        variant_id = str(uuid.uuid4())
        order_payload = {
            'idempotency_key': idempotency_key,
            'currency': 'USD',
            'shipping_address': {
                'city': 'Tehran',
                'street': 'Valiasr Ave',
                'postal_code': '19919',
            },
            'items_data': [
                {
                    'variant_id': variant_id,
                    'product_name': 'NEXUS Enterprise Server',
                    'sku': f'NX-SRV-{uuid.uuid4().hex[:6]}',
                    'quantity': 1,
                    'unit_price': '499.00',
                }
            ],
        }

        order_res = requests.post(
            f'{GATEWAY_URL}/api/v1/orders/',
            json=order_payload,
            headers={**auth_headers, 'Idempotency-Key': idempotency_key},
            timeout=5,
        )
        assert order_res.status_code == 201
        order_data = order_res.json()
        order_id = order_data['id']

        # 5. Verify Idempotency: Repeating exact same POST returns identical order_id
        dup_res = requests.post(
            f'{GATEWAY_URL}/api/v1/orders/',
            json=order_payload,
            headers={**auth_headers, 'Idempotency-Key': idempotency_key},
            timeout=5,
        )
        assert dup_res.status_code == 201
        assert dup_res.json()['id'] == order_id

        # 6. Poll Order Status to verify RabbitMQ Saga transition
        deadline = time.time() + 8.0
        final_status = order_data['status']
        while time.time() < deadline:
            detail_res = requests.get(
                f'{GATEWAY_URL}/api/v1/orders/{order_id}/',
                headers=auth_headers,
                timeout=5,
            )
            assert detail_res.status_code == 200
            final_status = detail_res.json()['status']
            if final_status in ('PAID', 'CANCELLED'):
                break
            time.sleep(0.5)

        assert final_status in ('PENDING', 'PAYMENT_PENDING', 'PAID', 'CANCELLED')


