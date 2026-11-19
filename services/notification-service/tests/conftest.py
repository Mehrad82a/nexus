import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from types import SimpleNamespace
import pytest



@pytest.fixture
def topology_config() -> SimpleNamespace:
    return SimpleNamespace(
        event_exchange='nexus.events',
        notification_queue='nexus.notification.delivery.queue',
        subscribed_routing_keys=(
            'payment.succeeded',
            'payment.failed',
            'order.cancelled',
        ),
        dead_letter_exchange='nexus.dlx',
        dead_letter_queue='nexus.notification.delivery.dlq',
        dead_letter_routing_key='notification.delivery.failed',
        prefetch_count=1,
    )




@pytest.fixture
def event_factory() -> Callable[..., dict[str, object]]:
    """
    Factory fixture for building valid NEXUS Saga event envelopes.
    """

    def _build_event(
        *,
        event_id: object | None = None,
        event_type: object = "payment.succeeded",
        order_id: object | None = None,
        user_id: object | None = None,
        payload_overrides: dict[str, object] | None = None,
    ) -> dict[str, object]:

        base_payload: dict[str, object] = {
            'order_id': str(uuid.uuid4()) if order_id is None else order_id,
            'user_id': str(uuid.uuid4()) if user_id is None else user_id,
            'amount': '1250.00',
            'currency': 'USD',
            'reason': 'CARD_DECLINED',
        }

        if payload_overrides:
            base_payload.update(payload_overrides)

        return {
            'event_id': str(uuid.uuid4()) if event_id is None else event_id,
            'event_type': event_type,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'payment-service',
            'version': '1.0',
            'payload': base_payload,
        }


    return _build_event

