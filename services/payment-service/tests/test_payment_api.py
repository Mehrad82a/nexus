import json
import uuid
from unittest.mock import MagicMock, patch
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.database import Base, async_engine, sync_engine
from app.core.security import compute_webhook_signature
from app.main import app
from app.messaging.services.handler import PaymentEventHandler
from app.models.payment import PaymentStatus
from app.service.locks import get_redis_client






def generate_test_jwt(user_id: uuid.UUID | None = None) -> tuple[str, uuid.UUID]:
    uid = user_id or uuid.uuid4()
    payload = {
        'user_id': str(uid),
        'email': 'customer@nexus.io',
        'role': 'CUSTOMER',
    }

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, uid



@pytest.fixture(autouse=True)
async def setup_database_and_cache():
    Base.metadata.create_all(bind=sync_engine)
    get_redis_client().flushdb()
    yield
    await async_engine.dispose()



class TestPaymentServiceAPIAndSaga:
    @patch('app.service.services.EventProducer.publish')
    async def test_idempotent_payment_prevents_double_change(self, mock_publish):
        token, _ = generate_test_jwt()
        headers = {'Authorization': f'Bearer {token}'}
        order_id = str(uuid.uuid4())
        payload = {
            'order_id': order_id,
            'idempotency_key': f'pay-idem-{uuid.uuid4()}',
            'amount': '1250.00',
            'currency': 'USD',
            'simulate_failure': False,
        }


        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            res1 = await client.post('/api/v1/payments/process', json=payload, headers=headers)
            assert res1.status_code == 201
            data1 = res1.json()
            assert data1['status'] == PaymentStatus.SUCCEEDED
            assert data1['provider_tx_id'].startswith('ch_mock_')
            assert mock_publish.call_count == 1

            res2 = await client.post('/api/v1/payments/process', json=payload, headers=headers)
            assert res2.status_code == 201
            data2 = res2.json()
            assert data2['id'] == data1['id']
            assert data2['provider_tx_id'] == data1['provider_tx_id']
            assert mock_publish.call_count == 1



    @patch('app.service.services.EventProducer.publish')
    async def test_webhook_hmac_signature_verification(self, mock_publish):
        token, _ = generate_test_jwt()
        order_id = str(uuid.uuid4())

        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            # Create initial failed payment
            await client.post(
                '/api/v1/payments/process',
                json={
                    'order_id': order_id,
                    'idempotency_key': f'idem-{uuid.uuid4()}',
                    'amount': '500.00',
                    'simulate_failure': True,
                },
                headers={'Authorization': f'Bearer {token}'},
            )


            webhook_payload = {
                'order_id': order_id,
                'provider_tx_id': 'ch_stripe_webhook_999',
                'event_status': 'SUCCEEDED',
            }

            raw_body = json.dumps(webhook_payload).encode('utf-8')


            # 1. Invalid signature must be rejected with 401
            bas_res = await client.post(
                '/api/v1/payments/webhook',
                content=raw_body,
                headers={
                    'Content-Type': 'application/json',
                    'X-Webhook-Signature': 'invalid_signature',
                },
            )
            assert bas_res.status_code == 401


            # 2. Valid HMAC-SHA256 signature succeeds and updates payment to SUCCEEDED
            valid_sig = compute_webhook_signature(raw_body)
            ok_res = await client.post(
                '/api/v1/payments/webhook',
                content=raw_body,
                headers={
                    'Content-Type': 'application/json',
                    'X-Webhook-Signature': valid_sig,
                },
            )
            assert ok_res.status_code == 200
            assert ok_res.json()['status'] == PaymentStatus.SUCCEEDED




    def test_payment_saga_consumer_handles_inventory_reserved(self):
        mock_producer = MagicMock()
        handler = PaymentEventHandler(producer=mock_producer)
        order_id = str(uuid.uuid4())

        event_envelope = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'inventory.reserved',
            'payload': {
                'order_id': order_id,
                'user_id': str(uuid.uuid4()),
                'total_amount': '999.00',
                'currency': 'USD',
            },
        }

        result = handler.process(event_envelope)
        assert result['status'] == PaymentStatus.SUCCEEDED
        mock_producer.publish.assert_called_once()
        assert mock_producer.publish.call_args.kwargs['event_type'] == 'payment.succeeded'


