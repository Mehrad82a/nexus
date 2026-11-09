import pika
from pika.adapters.blocking_connection import BlockingChannel

from orders.messaging.core.config import MessagingSettings, messaging_settings
from orders.messaging.services.exceptions import RabbitMQConnectionError
from orders.messaging.core.logger import get_logger

logger = get_logger(__name__)



class RabbitMQConnection:
    """
    Manage a blocking RabbitMQ connection and its channel.
    """

    def __init__(self, *, config: MessagingSettings | None = None) -> None:
        self._settings = config if config is not None else messaging_settings
        self.connection: pika.BlockingConnection | None = None
        self.channel: BlockingChannel | None = None


    def _create_parameters(self) -> pika.ConnectionParameters:
        credentials = pika.PlainCredentials(
            self._settings.rabbitmq_user,
            self._settings.rabbitmq_pass,
        )
        return pika.ConnectionParameters(
            host=self._settings.rabbitmq_host,
            port=self._settings.rabbitmq_port,
            virtual_host=self._settings.rabbitmq_virtual_host,
            credentials=credentials,
            heartbeat=self._settings.heartbeat,
            blocked_connection_timeout=self._settings.blocked_connection_timeout,
            connection_attempts=self._settings.connection_attempts,
            retry_delay=self._settings.retry_delay,
            socket_timeout=self._settings.socket_timeout,
        )


    def connect(self) -> BlockingChannel:
        """Return an open channel, establishing a connection when needed."""

        if self.connection is not None and self.connection.is_open:
            return self._open_channel()

        self.close()

        logger.info(
            '[RabbitMQConnection] Connecting: '
            f'host=<{self._settings.rabbitmq_host}> | '
            f'port=<{self._settings.rabbitmq_port}> | '
            f'virtual_host=<{self._settings.rabbitmq_virtual_host}>'
        )

        try:
            self.connection = pika.BlockingConnection(self._create_parameters())

        except (pika.exceptions.AMQPError, OSError) as exc:
            logger.exception('[RabbitMQConnection] Failed to establish connection.')
            raise RabbitMQConnectionError('Could not establish a RabbitMQ connection.') from exc

        channel = self._open_channel()
        logger.info('[RabbitMQConnection] Connection and channel are ready.')
        return channel



    def _open_channel(self) -> BlockingChannel:
        if self.channel is not None and self.connection.is_open:
            return self.channel

        connection = self.connection
        if connection is None or not connection.is_open:
            raise RabbitMQConnectionError('RabbitMQ connection is not available.')


        try:
            self.channel = connection.channel()


        except (pika.exceptions.AMQPError, OSError) as exc:
            self.close()

            logger.exception('[RabbitMQConnection] Failed to open channel.')
            raise RabbitMQConnectionError('Could not open a RabbitMQ channel.') from exc


        logger.info('[RabbitMQConnection] Channel opened.')
        return self.channel



    def close(self) -> None:
        connection = self.connection
        self.connection = None
        self.channel = None

        if connection is None or not connection.is_open:
            return

        logger.info('[RabbitMQConnection] Closing connection.')

        try:
            connection.close()

        except (pika.exceptions.AMQPError, OSError):
            logger.warning('[RabbitMQConnection] Connection cleanup failed.', exc_info=True)

        else:
            logger.info('[RabbitMQConnection] Connection closed.')




