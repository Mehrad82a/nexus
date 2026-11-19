from collections.abc import Callable
import pytest

from app.services.handler import NotificationEventHandler, get_redis_client
from tests.fakes.dispatchers import SuccessfulNotificationDispatcher




@pytest.fixture
def real_redis():
    client = get_redis_client()
    client.flushdb()
    yield client
    client.flushdb()



def test_real_redis_idempotency_prevents_duplicate_notification_delivery(
    real_redis,
    event_factory: Callable[..., dict[str, object]],
) -> None:
    dispatcher = SuccessfulNotificationDispatcher()
    handler = NotificationEventHandler(dispatcher=dispatcher, redis_client=real_redis)

    envelope = event_factory(event_type='payment.succeeded')

    # 1st delivery processes and stores event_id in real Redis DB 4
    first_result = handler.process(envelope)
    assert first_result['status'] == 'sent'
    assert len(dispatcher.calls) == 1

    # 2nd delivery (e.g., broker redelivery) hits real Redis and skips duplicate sending
    second_result = handler.process(envelope)
    assert second_result['status'] == 'duplicate_skipped'
    assert len(dispatcher.calls) == 1


