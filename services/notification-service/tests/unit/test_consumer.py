import json
from collections.abc import Callable
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from app.consumers.consumer import NotificationEventConsumer
from app.services.exceptions import (
    PermanentProcessingError,
    TransientProcessingError,
)



@pytest.fixture
def channel() -> MagicMock:
    mock_channel = MagicMock()
    mock_channel.is_open = True
    mock_channel.is_consuming = True
    return mock_channel


@pytest.fixture
def rabbitmq(channel: MagicMock) -> MagicMock:
    connection = MagicMock()
    connection.connect.return_value = channel
    return connection


@pytest.fixture
def topology() -> MagicMock:
    return MagicMock()


@pytest.fixture
def handler() -> MagicMock:
    return MagicMock()


@pytest.fixture
def consumer(
    topology_config: SimpleNamespace,
    rabbitmq: MagicMock,
    topology: MagicMock,
    handler: MagicMock,
) -> NotificationEventConsumer:
    return NotificationEventConsumer(
        config=topology_config,
        rabbitmq=rabbitmq,
        topology=topology,
        handler=handler,
    )


def build_delivery(*, delivery_tag: int = 1, redelivered: bool = False) -> SimpleNamespace:
    return SimpleNamespace(delivery_tag=delivery_tag, redelivered=redelivered)



def build_properties(*, message_id: str = 'msg-123') -> SimpleNamespace:
    return SimpleNamespace(message_id=message_id)



def test_callback_acknowledges_successful_event(
    consumer: NotificationEventConsumer,
    channel: MagicMock,
    handler: MagicMock,
    event_factory: Callable[..., dict[str, object]],
) -> None:
    envelope = event_factory()
    handler.process.return_value = {'status': 'sent'}

    consumer._callback(
        channel,
        build_delivery(),
        build_properties(),
        json.dumps(envelope).encode('utf-8'),
    )

    handler.process.assert_called_once_with(envelope)
    channel.basic_ack.assert_called_once_with(delivery_tag=1)
    channel.basic_nack.assert_not_called()
    channel.basic_reject.assert_not_called()



def test_callback_requeues_first_transient_failure(
    consumer: NotificationEventConsumer,
    channel: MagicMock,
    handler: MagicMock,
    event_factory: Callable[..., dict[str, object]],
) -> None:
    handler.process.side_effect = TransientProcessingError('Temporary SMTP error')

    consumer._callback(
        channel,
        build_delivery(redelivered=False),
        build_properties(),
        json.dumps(event_factory()).encode('utf-8'),
    )

    channel.basic_nack.assert_called_once_with(delivery_tag=1, requeue=True)
    channel.basic_ack.assert_not_called()
    channel.basic_reject.assert_not_called()



def test_callback_rejects_transient_failure_after_redelivery(
    consumer: NotificationEventConsumer,
    channel: MagicMock,
    handler: MagicMock,
    event_factory: Callable[..., dict[str, object]],
) -> None:
    handler.process.side_effect = TransientProcessingError('Temporary SMTP error')

    consumer._callback(
        channel,
        build_delivery(redelivered=True),
        build_properties(),
        json.dumps(event_factory()).encode('utf-8'),
    )

    channel.basic_reject.assert_called_once_with(delivery_tag=1, requeue=False)
    channel.basic_ack.assert_not_called()
    channel.basic_nack.assert_not_called()



def test_callback_rejects_permanent_failure_to_dlq(
    consumer: NotificationEventConsumer,
    channel: MagicMock,
    handler: MagicMock,
    event_factory: Callable[..., dict[str, object]],
) -> None:
    handler.process.side_effect = PermanentProcessingError('Malformed event')

    consumer._callback(
        channel,
        build_delivery(),
        build_properties(),
        json.dumps(event_factory()).encode('utf-8'),
    )

    channel.basic_reject.assert_called_once_with(delivery_tag=1, requeue=False)




def test_callback_rejects_malformed_json_bytes_to_dlq(
    consumer: NotificationEventConsumer,
    channel: MagicMock,
    handler: MagicMock,
) -> None:
    consumer._callback(
        channel,
        build_delivery(),
        build_properties(),
        b"not-valid-json",
    )

    handler.process.assert_not_called()
    channel.basic_reject.assert_called_once_with(delivery_tag=1, requeue=False)