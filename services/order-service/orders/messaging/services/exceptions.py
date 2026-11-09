

class RabbitMQConnectionError(Exception):
    """Raised when a usable RabbitMQ connection or channel cannot be opened."""


class ProducerPublishError(Exception):
    """Raised when an event cannot be published to RabbitMQ."""


class InvalidEventError(Exception):
    """Raised when event payload or envelope data is missing or invalid."""


class TransientProcessingError(Exception):
    """Raised when event processing may succeed on another attempt."""


class PermanentProcessingError(Exception):
    """Raised when retrying cannot make the event valid (routes immediately to DLQ)."""