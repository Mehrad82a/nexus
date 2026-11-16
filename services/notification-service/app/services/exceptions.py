

class RabbitMQConnectionError(Exception):
    """Raised when a usable RabbitMQ connection or channel cannot be opened."""


class InvalidEventError(Exception):
    """Raised when event envelope or payload data is missing or invalid."""


class TransientProcessingError(Exception):
    """Raised when notification delivery fails temporarily (e.g., SMTP/SMS gateway timeout)."""


class PermanentProcessingError(Exception):
    """Raised when retrying cannot make the notification valid (routes immediately to DLQ)."""