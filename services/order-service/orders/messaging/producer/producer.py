import json
import time
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone

import pika

from orders.messaging.core.config import MessagingSettings, messaging_settings
from orders.messaging.core.connection import RabbitMQConnection
from orders.messaging.services.exceptions import ProducerPublishError, RabbitMQConnectionError
from orders.messaging.core.logger import get_logger
from orders.messaging.core.topology import RabbitMQTopology


logger = get_logger(__name__)


class EventProducer:
    """
    Publish persistent domain events to the main topic exchange with Publisher Confirms.
    """

    def __init__(
        self,
        *,
        rabbitmq: RabbitMQConnection | None = None,
        topology: RabbitMQTopology | None = None,
        config: MessagingSettings | None = None,
    ) -> None:

        self._settings = config if config is not None else messaging_settings
        self._rabbitmq = rabbitmq if rabbitmq is not None else RabbitMQConnection(config=self._settings)
        self._topology = topology if topology is not None else RabbitMQTopology(config=self._settings)


    def publish(self, *, event_type: str, payload: Mapping[str, object]) -> str:
        """
        Build standard NEXUS event envelope, declare topology, enable confirm_delivery(),
        and publish persistent message.
        """

        if not isinstance(event_type, str) or not event_type.strip():
            raise ValueError('event_type must be a non-empty string.')

        event_id = str(uuid.uuid4())
        envelope = {
            'event_id': event_id,
            'event_type': event_type.strip(),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'source': 'order-service',
            'version': '1.0',
            'payload': dict(payload),
        }

        body = self._serialize_envelope(envelope)

        try:
            channel = self._rabbitmq.connect()
            self._topology.declare(channel)
            channel.confirm_delivery()

            channel.basic_publish(
                exchange=self._settings.event_exchange,
                routing_key=event_type.strip(),
                body=body,
                properties=pika.BasicProperties(
                    content_type="application/json",
                    content_encoding="utf-8",
                    delivery_mode=2,
                    type=event_type.strip(),
                    message_id=event_id,
                    timestamp=int(time.time()),
                ),
            )

        except (RabbitMQConnectionError, pika.exceptions.AMQPError, OSError) as exc:
            logger.exception(
                '[EventProducer] Event publish failed: '
                f'event_id=<{event_id}> | event_type=<{event_type}>'
            )
            raise ProducerPublishError('The event could not be published to RabbitMQ.') from exc

        finally:
            self._rabbitmq.close()


        logger.info(
            '[EventProducer] Event published: '
            f'event_id=<{event_id}> | event_type=<{event_type}>'
        )
        return event_id


    @staticmethod
    def _serialize_envelope(envelope: Mapping[str, object]) -> bytes:
        try:
            return json.dumps(
                dict(envelope),
                ensure_ascii=False,
                allow_nan=False,
                separators=(',', ':'),
            ).encode('utf-8')

        except (TypeError, ValueError) as exc:
            raise ProducerPublishError(
                'Event envelope contains values that cannot be serialized to JSON.'
            ) from exc


