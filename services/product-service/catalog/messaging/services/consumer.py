import json
from collections.abc import Mapping
import pika
from pika.adapters.blocking_connection import BlockingChannel

from catalog.messaging.core.config import MessagingSettings, messaging_settings
from catalog.messaging.core.connection import RabbitMQConnection
from catalog.messaging.services.exceptions import (
    PermanentProcessingError,
    TransientProcessingError,
)
from catalog.messaging.services.handler import InventoryEventHandler
from catalog.messaging.core.logger import get_logger
from catalog.messaging.core.topology import RabbitMQTopology


logger = get_logger(__name__)



class InventoryEventConsumer:
    """
    Consume Saga events with manual acknowledgments, transient retry, and DLQ routing.
    """

    def __init__(
        self,
        *,
        handler: InventoryEventHandler | None = None,
        rabbitmq: RabbitMQConnection | None = None,
        topology: RabbitMQTopology | None = None,
        config: MessagingSettings | None = None,
    ) -> None:

        self._settings = config if config is not None else messaging_settings
        self._handler = handler if handler is not None else InventoryEventHandler()
        self._rabbitmq = rabbitmq if rabbitmq is not None else RabbitMQConnection(config=self._settings)
        self._topology = topology if topology is not None else RabbitMQTopology(config=self._settings)
        self._channel: BlockingChannel | None = None


    def start(self) -> None:
        """Declare topology and consume until stopped."""

        try:
            channel = self._rabbitmq.connect()
            self._channel = channel

            self._topology.declare(channel)
            channel.basic_qos(prefetch_count=self._settings.prefetch_count)

            channel.basic_consume(
                queue=self._settings.inventory_queue,
                on_message_callback=self._callback,
                auto_ack=False,
            )

            logger.info(f'[InventoryEventConsumer] Waiting for events: queue=<{self._settings.inventory_queue}>')

            channel.start_consuming()

        finally:
            self._channel = None
            self._rabbitmq.close()



    def stop(self) -> None:
        """Stop consuming; start() will close the connection."""
        channel = self._channel

        if channel is not None and channel.is_open and channel.is_consuming:
            channel.stop_consuming()

    def _callback(
        self,
        channel: BlockingChannel,
        method: pika.spec.Basic.Deliver,
        properties: pika.BasicProperties,
        body: bytes,
    ) -> None:

        delivery_tag = method.delivery_tag

        try:
            envelope = self._deserialize(body)

        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            logger.exception(
                f'[InventoryEventConsumer] Invalid JSON message: delivery_tag=<{delivery_tag}>'
            )
            self._reject(channel, delivery_tag, reason='invalid_message')
            return

        event_id = self._event_id(envelope)


        try:
            result = self._handler.process(envelope)

        except TransientProcessingError:
            if method.redelivered:
                logger.exception(f'[InventoryEventConsumer] Transient failure on redelivery: event_id=<{event_id}>')
                self._reject(channel, delivery_tag, reason='transient_failure_on_redelivery')

            else:
                logger.warning(
                    f'[InventoryEventConsumer] Transient failure; requeueing: event_id=<{event_id}>',
                    exc_info=True,
                )
                channel.basic_nack(delivery_tag=delivery_tag, requeue=True)
            return


        except PermanentProcessingError:
            logger.exception(f'[InventoryEventConsumer] Permanent failure: event_id=<{event_id}>')
            self._reject(channel, delivery_tag, reason='permanent_failure')
            return

        except Exception:
            logger.exception(f'[InventoryEventConsumer] Unexpected processing failure: event_id=<{event_id}>')
            self._reject(channel, delivery_tag, reason='unexpected_failure')
            return


        channel.basic_ack(delivery_tag=delivery_tag)
        logger.info(f'[InventoryEventConsumer] Event acknowledged: event_id=<{event_id}> | result=<{result}>')




    @staticmethod
    def _deserialize(body: bytes) -> dict[str, object]:
        data = json.loads(body.decode('utf-8'))

        if not isinstance(data, dict):
            raise ValueError('Event body must be a JSON object.')

        return data



    @staticmethod
    def _event_id(envelope: Mapping[str, object]) -> str:
        value = envelope.get('event_id')

        if isinstance(value, str) and value.strip():
            return value.strip()

        return 'unknown'



    @staticmethod
    def _reject(channel: BlockingChannel, delivery_tag: int, *, reason: str) -> None:
        channel.basic_reject(delivery_tag=delivery_tag, requeue=False)
        logger.error(
            f'[InventoryEventConsumer] Message rejected to DLQ: '
            f'delivery_tag=<{delivery_tag}> | reason=<{reason}>'
        )


