from pika.adapters.blocking_connection import BlockingChannel

from catalog.messaging.core.config import MessagingSettings, messaging_settings
from catalog.messaging.core.logger import get_logger

logger = get_logger(__name__)



class RabbitMQTopology:
    """
    Declare the main event topic topology and the dead-letter destination.
    """

    def __init__(self, *, config: MessagingSettings | None = None) -> None:
        self._settings = config if config is not None else messaging_settings

        if self._settings.inventory_queue == self._settings.dead_letter_queue:
            raise ValueError('The main queue and dead-letter queue must be different.')


    def declare(self, channel: BlockingChannel) -> None:
        """
        Declare exchanges, queues, and bindings using an open channel.
        The dead-letter destination is declared before the main queue.
        """

        if not channel.is_open:
            raise RuntimeError('An open RabbitMQ channel is required to declare topology.')

        self._declare_dead_letter_topology(channel)
        self._declare_event_topology(channel)

        logger.info('[RabbitMQTopology] Topology is ready.')



    def _declare_dead_letter_topology(self, channel: BlockingChannel) -> None:
        channel.exchange_declare(
            exchange=self._settings.dead_letter_exchange,
            exchange_type='direct',
            durable=True,
        )

        channel.queue_declare(
            queue=self._settings.dead_letter_queue,
            durable=True,
            exclusive=False,
            auto_delete=False,
        )

        channel.queue_bind(
            queue=self._settings.dead_letter_queue,
            exchange=self._settings.dead_letter_exchange,
            routing_key=self._settings.dead_letter_routing_key,
        )

        logger.info(
            '[RabbitMQTopology] Dead-letter destination declared: '
            f'exchange=<{self._settings.dead_letter_exchange}> | '
            f'queue=<{self._settings.dead_letter_queue}> | '
            f'routing_key=<{self._settings.dead_letter_routing_key}>'
        )



    def _declare_event_topology(self, channel: BlockingChannel) -> None:
        channel.exchange_declare(
            exchange=self._settings.event_exchange,
            exchange_type='topic',
            durable=True,
        )

        channel.queue_declare(
            queue=self._settings.inventory_queue,
            durable=True,
            exclusive=False,
            auto_delete=False,
            arguments={
                'x-dead-letter-exchange': self._settings.dead_letter_exchange,
                'x-dead-letter-routing-key': self._settings.dead_letter_routing_key,
            },
        )

        for routing_key in self._settings.subscribed_routing_keys:
            channel.queue_bind(
                queue=self._settings.inventory_queue,
                exchange=self._settings.event_exchange,
                routing_key=routing_key,
            )

        logger.info(
            '[RabbitMQTopology] Event destination declared: '
            f'exchange=<{self._settings.event_exchange}> | '
            f'queue=<{self._settings.inventory_queue}>'
        )

