from app.core.logger import get_logger
from app.services.exceptions import InvalidEventError


logger = get_logger(__name__)




class DefaultNotificationDispatcher:
    """
    Simulates external Email/SMS gateway delivery with structured logging.
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
        if not user_id.strip() or not order_id.strip():
            raise InvalidEventError('user_id and order_id must not be blank.')

        logger.info(
            f'[NotificationDispatcher] Dispatched {channel_type}: '
            f'user_id=<{user_id}> | order_id=<{order_id}> | subject=<{subject}>'
        )

        return {
            'user_id': user_id,
            'order_id': order_id,
            'channel': channel_type,
            'subject': subject,
            'status': 'sent',
        }

