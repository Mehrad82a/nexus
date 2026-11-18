from typing import Protocol


class NotificationDispatcher(Protocol):
    """
    Protocol contract for notification delivery implementations (Email, SMS, Push).
    """

    def send(
        self,
        *,
        user_id: str,
        order_id: str,
        channel_type: str,
        subject: str,
        message: str,
    ) -> dict[str, object]:
        ...

