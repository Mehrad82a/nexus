from types import SimpleNamespace
from unittest.mock import MagicMock, call
import pytest

from app.core.topology import RabbitMQTopology




def test_declare_creates_dead_letter_and_topic_event_topology(
    topology_config: SimpleNamespace,
) -> None:
    channel = MagicMock()
    channel.is_open = True

    topology = RabbitMQTopology(config=topology_config)
    topology.declare(channel)

    assert channel.exchange_declare.call_args_list == [
        call(
            exchange='nexus.dlx',
            exchange_type='direct',
            durable=True,
        ),
        call(
            exchange='nexus.events',
            exchange_type='topic',
            durable=True,
        )
    ]

    assert channel.queue_declare.call_args_list == [
        call(
            queue='nexus.notification.delivery.dlq',
            durable=True,
            exclusive=False,
            auto_delete=False,
        ),
        call(
            queue='nexus.notification.delivery.queue',
            durable=True,
            exclusive=False,
            auto_delete=False,
            arguments={
                'x-dead-letter-exchange': 'nexus.dlx',
                'x-dead-letter-routing-key': 'notification.delivery.failed',
            },
        ),
    ]

    assert channel.queue_bind.call_count == 4



def test_declare_rejects_closed_channel(topology_config: SimpleNamespace) -> None:
    channel = MagicMock()
    channel.is_open = False

    topology = RabbitMQTopology(config=topology_config)

    with pytest.raises(RuntimeError, match='open RabbitMQ channel'):
        topology.declare(channel)



def test_constructor_rejects_identical_main_and_dlq_queues(
    topology_config: SimpleNamespace,
) -> None:
    topology_config.dead_letter_queue = topology_config.notification_queue

    with pytest.raises(ValueError, match='must be different'):
        RabbitMQTopology(config=topology_config)


