import uuid
from collections.abc import Mapping
import redis

from app.core.config import MessagingSettings, messaging_settings
from app.core.logger import get_logger
from app.services.contracts import NotificationDispatcher
from app.services.dispatcher import DefaultNotificationDispatcher
from app.services.exceptions import (
    InvalidEventError,
    PermanentProcessingError,
    TransientProcessingError,
)



logger = get_logger(__name__)




def get_redis_client(config: MessagingSettings | None = None) -> redis.Redis:
    cfg = config if config is not None else messaging_settings
    return redis.Redis(
        host=cfg.redis_host,
        port=cfg.redis_port,
        password=cfg.redis_password,
        db=cfg.redis_db,
        decode_responses=True,
    )


class NotificationEventHandler:
    """
    Validate incoming Saga events, enforce Redis idempotency, dispatch Email/SMS
    notifications, and classify failures into Transient vs. Permanent for the Consumer.
    """

    def __init__(
        self,
        *,
        dispatcher: DefaultNotificationDispatcher | None = None,
        redis_client: redis.Redis | None = None,
    ) -> None:
        self._dispatcher = dispatcher if dispatcher is not None else DefaultNotificationDispatcher()
        self._redis = redis_client


    def _get_redis(self) -> redis.Redis:
        if self._redis is not None:
            return self._redis

        return get_redis_client()


    def process(self, envelope:Mapping[str, object]) -> dict[str, object]:
        try:
            event_id = self._get_required_str(envelope, 'event_id')
            event_type = self._get_required_str(envelope, 'event_type')
            payload = envelope.get('payload')

            if not isinstance(payload, dict):
                raise InvalidEventError('Event payload must be a JSON object.')

            order_id_str = self._get_required_str(payload, 'order_id')
            user_id_str = self._get_required_str(payload, 'user_id')
            uuid.UUID(order_id_str)
            uuid.UUID(user_id_str)

        except (InvalidEventError, ValueError) as exc:
            raise PermanentProcessingError(f'Malformed event envelope: {exc}') from exc

        dedup_key = f'nexus:notification:processed_event:{event_id}'
        redis_conn = self._get_redis()
        if redis_conn.get(dedup_key):
            logger.info(f'[NotificationEventHandler] Duplicate event skipped: event_id=<{event_id}>')
            return {
                'event_id': event_id,
                'status': 'duplicate_skipped',
            }


        try:
            result = self._dispatch(
                event_type=event_type,
                order_id=order_id_str,
                user_id=user_id_str,
                payload=payload,
            )

        except (TimeoutError, ConnectionError) as exc:
            raise TransientProcessingError(
                f'Temporary notification provider timeout for event <{event_id}>.'
            ) from exc

        except InvalidEventError as exc:
            raise PermanentProcessingError(f'Invalid notification data: {exc}') from exc

        redis_conn.set(dedup_key, '1', ex=60 * 60 * 24)
        return result



    def _dispatch(
        self,
        *,
        event_type: str,
        order_id: str,
        user_id: str,
        payload: dict[str, object],
    ) -> dict[str, object]:

        if event_type == 'payment.succeeded':
            amount = str(payload.get('amount', '0.00'))
            return self._dispatcher.send(
                user_id=user_id,
                order_id=order_id,
                channel_type='EMAIL_AND_SMS',
                subject='Order Confirmed & Payment Received',
                message=f'Your payment of {amount} USD for order {order_id} was successful.',
            )

        elif event_type == 'payment.failed':
            reason = str(payload.get('reason', 'PAYMENT_DECLINED'))
            return self._dispatcher.send(
                user_id=user_id,
                order_id=order_id,
                channel_type="EMAIL",
                subject='Payment Failed for Your Order',
                message=f'Payment for order {order_id} failed ({reason}).',
            )


        elif event_type == 'order.cancelled':
            reason = str(payload.get('reason', 'Cancelled'))
            return self._dispatcher.send(
                user_id=user_id,
                order_id=order_id,
                channel_type='EMAIL',
                subject='Order Cancelled',
                message=f'Your order {order_id} has been cancelled ({reason}).',
            )

        raise PermanentProcessingError(f'Unsupported event_type: {event_type}')



    @staticmethod
    def _get_required_str(data: Mapping[str, object], field_name: str) -> str:
        value = data.get(field_name)

        if not isinstance(value, str) or not value.strip():
            raise InvalidEventError(f'Missing or blank required field: {field_name}')

        return value.strip()



