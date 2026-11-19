from app.services.exceptions import InvalidEventError



class SuccessfulNotificationDispatcher:
    """A fake dispatcher that records calls and always succeeds."""

    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def send(
        self,
        *,
        user_id: str,
        order_id: str,
        channel_type: str,
        subject: str,
        message: str,
    ) -> dict[str, object]:
        record = {
            'user_id': user_id,
            'order_id': order_id,
            'channel': channel_type,
            'subject': subject,
            'message': message,
            'status': 'sent',
        }
        self.calls.append(record)
        return record



class TemporaryFailingNotificationDispatcher:
    """A fake dispatcher that simulates a transient SMTP/SMS gateway timeout."""

    def send(
        self,
        *,
        user_id: str,
        order_id: str,
        channel_type: str,
        subject: str,
        message: str,
    ) -> dict[str, object]:
        raise TimeoutError(
            f'Temporary SMTP gateway timeout while notifying user <{user_id}> for order <{order_id}>.'
        )



class PermanentlyFailingNotificationDispatcher:
    """A fake dispatcher that simulates an unrecoverable validation failure."""

    def send(
        self,
        *,
        user_id: str,
        order_id: str,
        channel_type: str,
        subject: str,
        message: str,
    ) -> dict[str, object]:
        raise InvalidEventError(
            f'Notification recipient for user <{user_id}> violates domain policy.'
        )