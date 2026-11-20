import json
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

from catalog.messaging.core.topology import RabbitMQTopology
from catalog.messaging.producer.producer import EventProducer
from catalog.messaging.services.consumer import InventoryEventConsumer
from catalog.messaging.services.exceptions import (
    PermanentProcessingError,
    ProducerPublishError,
    TransientProcessingError,
)


@pytest.fixture
def mock_config() -> SimpleNamespace:
    return SimpleNamespace(
        event_exchange='nexus.events',
        inventory_queue='nexus.product.inventory.queue',
        subscribed_routing_keys=('order.created', 'payment.failed'),
        dead_letter_exchange='nexus.dlx',
        dead_letter_queue='nexus.product.inventory.dlq',
        dead_letter_routing_key='product.inventory.failed',
        prefetch_count=1,
    )


def test_topology_declares_dlx_and_topic_exchange(mock_config: SimpleNamespace):
    channel = MagicMock()
    channel.is_open = True

    topology = RabbitMQTopology(config=mock_config)
    topology.declare(channel)

    assert channel.exchange_declare.call_count == 2
    assert channel.queue_declare.call_count == 2
    assert channel.queue_bind.call_count == 3   # 1 DLQ bind + 2 routing keys



def test_producer_publishes_persistent_event_with_confirms(mock_config: SimpleNamespace):
    channel = MagicMock()
    rabbitmq = MagicMock()
    rabbitmq.connect.return_value = channel
    topology = MagicMock()

    producer = EventProducer(config=mock_config, rabbitmq=rabbitmq, topology=topology)
    event_id = producer.publish(event_type='inventory.reserved', payload={'order_id': '123'})

    assert event_id
    topology.declare.assert_called_once_with(channel)
    channel.confirm_delivery.assert_called_once()
    channel.basic_publish.assert_called_once()

    publish_kwargs = channel.basic_publish.call_args.kwargs
    assert publish_kwargs['exchange'] == 'nexus.events'
    assert publish_kwargs['routing_key'] == 'inventory.reserved'
    assert publish_kwargs['properties'].delivery_mode == 2
    rabbitmq.close.assert_called_once()



def test_producer_wraps_broker_error(mock_config: SimpleNamespace):
    rabbitmq = MagicMock()
    rabbitmq.connect.side_effect = OSError('Broker down')
    topology = MagicMock()

    producer = EventProducer(config=mock_config, rabbitmq=rabbitmq, topology=topology)
    with pytest.raises(ProducerPublishError):
        producer.publish(event_type='inventory.reserved', payload={'order_id': '123'})

    rabbitmq.close.assert_called_once()



def test_consumer_requeues_first_transient_error_and_rejects_redelivered(mock_config: SimpleNamespace):
    channel = MagicMock()
    handler = MagicMock()
    handler.process.side_effect = TransientProcessingError('DB lock timeout')

    consumer = InventoryEventConsumer(
        config=mock_config,
        rabbitmq=MagicMock(),
        topology=MagicMock(),
        handler=handler,
    )

    body = json.dumps({
        'event_id': 'evt-1',
        'event_type': 'order.created',
    }).encode('utf-8')


    # 1st attempt (redelivered=False) -> NACK with requeue=True
    consumer._callback(
        channel,
        SimpleNamespace(delivery_tag=1, redelivered=False),
        SimpleNamespace(message_id='evt-1'),
        body,
    )
    channel.basic_nack.assert_called_once_with(delivery_tag=1, requeue=True)

    # 2nd attempt (redelivered=True) -> Reject to DLQ (requeue=False)
    consumer._callback(
        channel,
        SimpleNamespace(delivery_tag=2, redelivered=True),
        SimpleNamespace(message_id='evt-1'),
        body
    )
    channel.basic_reject.assert_called_once_with(delivery_tag=2, requeue=False)



def test_consumer_rejects_permanent_error_to_dlq(mock_config: SimpleNamespace):
    channel = MagicMock()
    handler = MagicMock()
    handler.process.side_effect = PermanentProcessingError('Invalid payload')

    consumer = InventoryEventConsumer(
        config=mock_config,
        rabbitmq=MagicMock(),
        topology=MagicMock(),
        handler=handler,
    )

    body = json.dumps({
        'event_id': 'evt-2',
        'event_type': 'order.created',
    }).encode('utf-8')

    consumer._callback(
        channel,
        SimpleNamespace(delivery_tag=5, redelivered=False),
        SimpleNamespace(message_id='evt-2'),
        body,
    )

    channel.basic_reject.assert_called_once_with(delivery_tag=5, requeue=False)





