from collections.abc import Callable
from unittest.mock import MagicMock
import pytest

from app.services.exceptions import (
    PermanentProcessingError,
    TransientProcessingError,
)
from app.services.handler import NotificationEventHandler
from tests.fakes.dispatchers import (
    PermanentlyFailingNotificationDispatcher,
    SuccessfulNotificationDispatcher,
    TemporaryFailingNotificationDispatcher,
)



@pytest.mark.parametrize(
    ('event_type', 'expected_channel', 'expected_subject'),
    [
        ('payment.succeeded', 'EMAIL_AND_SMS', 'Order Confirmed & Payment Received'),
        ('payment.failed', 'EMAIL', 'Payment Failed for Your Order'),
        ('order.cancelled', 'EMAIL', 'Order Cancelled'),
    ],
)
def test_process_routes_supported_events_to_dispatcher(
        event_factory: Callable[..., dict[str, object]],
        event_type: str,
        expected_channel: str,
        expected_subject: str,
) -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = None
    fake_dispatcher = SuccessfulNotificationDispatcher()

    handler = NotificationEventHandler(
        dispatcher=fake_dispatcher,
        redis_client=mock_redis,
    )

    envelope = event_factory(event_type=event_type)
    result = handler.process(envelope)

    assert result['status'] == 'sent'
    assert result['channel'] == expected_channel
    assert result['subject'] == expected_subject
    assert len(fake_dispatcher.calls) == 1
    mock_redis.set.assert_called_once()




def test_process_skips_duplicate_event_id_via_redis(
    event_factory: Callable[..., dict[str, object]],
) -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = '1'
    fake_dispatcher = SuccessfulNotificationDispatcher()

    handler = NotificationEventHandler(
        dispatcher=fake_dispatcher,
        redis_client=mock_redis,
    )

    envelope = event_factory()
    result = handler.process(envelope)

    assert result == {
        'event_id': envelope['event_id'],
        'status': 'duplicate_skipped',
    }
    assert len(fake_dispatcher.calls) == 0




def test_process_converts_timeout_to_transient_processing_error(
    event_factory: Callable[..., dict[str, object]],
) -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = None

    handler = NotificationEventHandler(
        dispatcher=TemporaryFailingNotificationDispatcher(),
        redis_client=mock_redis,
    )

    with pytest.raises(TransientProcessingError, match='Temporary notification provider timeout'):
        handler.process(event_factory())




def test_process_converts_invalid_event_to_permanent_processing_error(
    event_factory: Callable[..., dict[str, object]],
) -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = None

    handler = NotificationEventHandler(
        dispatcher=PermanentlyFailingNotificationDispatcher(),
        redis_client=mock_redis,
    )

    with pytest.raises(PermanentProcessingError, match='Invalid notification data'):
        handler.process(event_factory())




def test_process_rejects_unsupported_event_type(
    event_factory: Callable[..., dict[str, object]],
) -> None:
    mock_redis = MagicMock()
    mock_redis.get.return_value = None

    handler = NotificationEventHandler(
        dispatcher=SuccessfulNotificationDispatcher(),
        redis_client=mock_redis,
    )

    with pytest.raises(PermanentProcessingError, match='Unsupported event_type'):
        handler.process(event_factory(event_type='unknown.event'))

