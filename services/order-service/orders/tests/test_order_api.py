import uuid
from unittest.mock import patch
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from orders.messaging.services.handler import OrderEventHandler
from orders.models import Order
from orders.service.locks import DistributedLockConflictError, redis_distributed_lock
from orders.state_machine import (
    InvalidOrderStateTransitionError,
    OrderStateMachine,
    OrderStatus,
)



def generate_customer_jwt(user_id: uuid.UUID | None = None) -> tuple[str, uuid.UUID]:
    uid = user_id or uuid.uuid4()
    token = RefreshToken()
    token['user_id'] = str(uid)
    token['email'] = 'customer@nexus.io'
    token['role'] = 'CUSTOMER'
    return str(token.access_token), uid




@pytest.fixture
def api_client() -> APIClient:
    cache.clear()
    return APIClient()



@pytest.fixture
def order_payload() -> dict:
    return {
        'idempotency_key': f'idem-{uuid.uuid4()}',
        'currency': 'USD',
        'shipping_address': {'city': 'Tehran', 'street': 'Valiasr', 'postal_code': '12345'},
        'items_data': [
            {
                'variant_id': str(uuid.uuid4()),
                'product_name': 'iPhone 16 Pro',
                'sku': 'IP16P-256-BLK',
                'quantity': 2,
                'unit_price': '1099.00',
            }
        ],
    }


def test_order_state_machine_enforces_valid_transition():
    OrderStateMachine.validate_transition(
        from_status=OrderStatus.PENDING,
        to_status=OrderStatus.PAYMENT_PENDING,
    )

    OrderStateMachine.validate_transition(
        from_status=OrderStatus.PAYMENT_PENDING,
        to_status=OrderStatus.PAID,
    )

    with pytest.raises(InvalidOrderStateTransitionError):
        OrderStateMachine.validate_transition(
            from_status=OrderStatus.CANCELLED,
            to_status=OrderStatus.PAID,
        )




@pytest.mark.django_db
class TestOrderServiceAPIAndSaga:
    @patch('orders.service.services.EventProducer.publish')
    def test_create_order_idempotency_and_snapshot(self, mock_publish, api_client: APIClient, order_payload: dict):
        token, user_id = generate_customer_jwt()
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        url = reverse('orders:order_list_create')


        # 1st Request creates the order and publishes order.created
        res1 = api_client.post(url, data=order_payload, format='json')
        assert res1.status_code == status.HTTP_201_CREATED
        assert res1.data['status'] == OrderStatus.PENDING
        assert res1.data['total_amount'] == '2198.00'
        assert len(res1.data['items']) == 1
        assert res1.data['items'][0]['subtotal'] == '2198.00'
        assert mock_publish.call_count == 1


        # 2nd Request with same idempotency_key returns existing order without duplicate DB/publish
        res2 = api_client.post(url, data=order_payload, format='json')
        assert res2.status_code == status.HTTP_201_CREATED
        assert res2.data['id'] == res1.data['id']
        assert Order.objects.filter(user_id=user_id).count() == 1
        assert mock_publish.call_count == 1


    def test_redis_distributed_lock_blocks_concurrent_acquisition(self):
        lock_key = f'test-lock-{uuid.uuid4()}'
        with redis_distributed_lock(lock_key, ttl_seconds=10):
            with pytest.raises(DistributedLockConflictError):
                with redis_distributed_lock(lock_key, ttl_seconds=10):
                    pass



    @patch('orders.service.services.EventProducer.publish')
    def test_order_saga_lifecycle_from_pending_to_paid(self, mock_publish, api_client: APIClient, order_payload: dict):
        token, _ = generate_customer_jwt()
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        create_res = api_client.post(reverse('orders:order_list_create'), data=order_payload, format='json')
        order_id = create_res.data['id']

        handler = OrderEventHandler()


        # Step 1: inventory.reserved -> transitions order to PAYMENT_PENDING
        handler.process(
            {
                'event_id': str(uuid.uuid4()),
                'event_type': 'inventory.reserved',
                'payload': {'order_id': order_id},
            }
        )
        order = Order.objects.get(id=order_id)
        assert order.status == OrderStatus.PAYMENT_PENDING


        # Step 2: payment.succeeded -> transitions order to PAID
        handler.process(
            {
                'event_id': str(uuid.uuid4()),
                'event_type': 'payment.succeeded',
                'payload': {'order_id': order_id, 'provider_tx_id': 'ch_mock_123'},
            }
        )
        order.refresh_from_db()
        assert order.status == OrderStatus.PAID
        assert order.status_history.count() == 3


        # Step 3: Attempting to cancel a PAID order must fail with 400
        cancel_url = reverse('orders:order_cancel', kwargs={'order_id': order_id})
        cancel_res = api_client.post(cancel_url, data={'reason': 'Changed mind'}, format='json')
        assert cancel_res.status_code == status.HTTP_400_BAD_REQUEST



