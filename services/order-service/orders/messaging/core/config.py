import os
from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class MessagingSettings:
    rabbitmq_host: str = field(default_factory=lambda: os.environ.get('RABBITMQ_HOST', 'rabbitmq'))
    rabbitmq_port: int = field(default_factory=lambda: int(os.environ.get('RABBITMQ_PORT', '5672')))
    rabbitmq_user: str = field(default_factory=lambda: os.environ.get('RABBITMQ_DEFAULT_USER', 'nexus_mq'))
    rabbitmq_pass: str = field(
        default_factory=lambda: os.environ.get('RABBITMQ_DEFAULT_PASS', 'admin_pass')
    )
    rabbitmq_virtual_host: str = field(default_factory=lambda: os.environ.get('RABBITMQ_VHOST', '/'))

    heartbeat: int = 600
    blocked_connection_timeout: int = 300
    connection_attempts: int = 10
    retry_delay: int = 5
    socket_timeout: int = 10

    # Main Event Topology (Topic Exchange)
    event_exchange: str = 'nexus.events'
    order_queue: str = 'nexus.order.saga.queue'
    subscribed_routing_keys: Tuple[str, ...] = (
        'inventory.reserved',
        'inventory.rejected',
        'payment.succeeded',
        'payment.failed',
    )

    # Dead-Letter Topology
    dead_letter_exchange: str = 'nexus.dlx'
    dead_letter_queue: str = 'nexus.order.saga.dlq'
    dead_letter_routing_key: str = 'order.saga.failed'

    # Consumer QOS
    prefetch_count: int = 1


messaging_settings = MessagingSettings()