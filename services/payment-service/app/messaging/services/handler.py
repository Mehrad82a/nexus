import uuid
from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from sqlalchemy.exc import OperationalError

from app.core.database import Base, SyncSessionLocal, sync_engine
from app.messaging.core.logger import get_logger
from app.messaging.producer.producer import EventProducer
from app.messaging.services.exceptions import (
    InvalidEventError,
    PermanentProcessingError,
    TransientProcessingError,
)
from app.service.locks import get_redis_client
from app.service.services import PaymentService



logger = get_logger(__name__)




class PaymentEventHandler:
    """
    Consume 'inventory.reserved' Saga events, enforce Redis idempotency,
    execute PaymentService.process_payment_sync, and classify failures for DLQ routing.
    """

    def __init__(self, *, producer: EventProducer | None = None) -> None:
        self._producer = producer if producer is not None else EventProducer()
        Base.metadata.create_all(bind=sync_engine)


    def process(self, envelope:Mapping[str, object]) -> dict[str, object]:
        try:
            event_id = self._get_required_str(envelope, 'event_id')
            event_type = self._get_required_str(envelope, 'event_type')
            payload = envelope.get('payload')

            if not isinstance(payload, dict):
                raise InvalidEventError('Event payload must be a JSON object.')

            order_id_str = self._get_required_str(payload, 'order_id')
            order_id = uuid.UUID(order_id_str)

        except (InvalidEventError, ValueError) as exc:
            raise PermanentProcessingError(f'Malformed event envelope: {exc}') from exc


        redis_client = get_redis_client()
        dedup_key = f'nexus:payment:processed_event:{event_id}'
        if redis_client.get(dedup_key):
            logger.info(f'[PaymentEventHandler] Duplicate event skipped: event_id=<{event_id}>')
            return {
                'event_id': event_id,
                'status': 'duplicate_skipped',
            }


        try:
            result = self._dispatch(event_type=event_type, order_id=order_id, payload=payload)

        except (OperationalError, TimeoutError, ConnectionError) as exc:
            raise TransientProcessingError(
                f'Transient infrastructure failure while processing event <{event_id}>.'
            ) from exc

        redis_client.set(dedup_key, '1', ex=60 * 60 * 24)
        return result



    def _dispatch(
        self,
        *,
        event_type: str,
        order_id: uuid.UUID,
        payload: dict[str, object],
    ) -> dict[str, object]:

        if event_type == 'inventory.reserved':
            try:
                user_id = uuid.UUID(self._get_required_str(payload, 'user_id'))
                total_amount_str = self._get_required_str(payload, 'total_amount')
                amount = Decimal(total_amount_str)

                if amount <= Decimal('0.00'):
                    raise InvalidEventError('total_amount must be greater than zero.')


            except (InvalidEventError, ValueError, InvalidOperation) as exc:
                raise PermanentProcessingError(f'Invalid inventory.reserved payload: {exc}') from exc


            currency = str(payload.get('currency', 'USD'))
            simulate_failure = bool(payload.get('simulate_failure', False))

            with SyncSessionLocal() as session:
                payment = PaymentService.process_payment_sync(
                    session,
                    order_id=order_id,
                    user_id=user_id,
                    idempotency_key=f'saga-order-{order_id}',
                    amount=amount,
                    currency=currency,
                    simulate_failure=simulate_failure,
                    producer=self._producer,
                )

            return {
                'order_id': str(order_id),
                'payment_id': str(payment.id),
                'status': payment.status,
            }

        raise PermanentProcessingError(f'Unsupported event_type: {event_type}')



    @staticmethod
    def _get_required_str(data: Mapping[str, object], field_name: str) -> str:
        value = data.get(field_name)

        if not isinstance(value, str) or not value.strip():
            raise InvalidEventError(f'Missing or blank required field: {field_name}')

        return value.strip()
