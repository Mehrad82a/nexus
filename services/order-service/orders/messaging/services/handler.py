import uuid
from collections.abc import Mapping
from django.core.cache import cache
from django.db import OperationalError
from rest_framework.exceptions import NotFound, ValidationError

from orders.messaging.core.logger import get_logger
from orders.messaging.services.exceptions import (
    InvalidEventError,
    PermanentProcessingError,
    TransientProcessingError,
)
from orders.service.services import OrderService
from orders.state_machine import OrderStatus


logger = get_logger(__name__)



class OrderEventHandler:
    """
    Validate incoming Saga events, enforce Redis idempotency, transition Order status
    via OrderService, and classify failures into Transient vs. Permanent for the Consumer.
    """

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


        dedup_key = f'nexus:order:processed_event:{event_id}'
        if cache.get(dedup_key):
            logger.info(f'[OrderEventHandler] Duplicate event skipped: event_id=<{event_id}>')
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

        except (NotFound, ValidationError) as exc:
            raise PermanentProcessingError(f'Domain error processing event <{event_id}>: {exc}') from exc


        cache.set(dedup_key, '1', timeout=60 * 60 * 24)
        return result


    def _dispatch(
        self,
        *,
        event_type: str,
        order_id: uuid.UUID,
        payload: dict[str, object],
    ) -> dict[str, object]:

        if event_type == 'inventory.reserved':
            OrderService.transition_order_status(
                order_id=order_id,
                to_status=OrderStatus.PAYMENT_PENDING,
                reason='Inventory reserved; awaiting payment processing.',
            )
            return {'order_id': str(order_id), 'status': OrderStatus.PAYMENT_PENDING}



        elif event_type == 'inventory.rejected':
            reason = str(payload.get('reason', 'INSUFFICIENT_STOCK'))

            OrderService.transition_order_status(
                order_id=order_id,
                to_status=OrderStatus.CANCELLED,
                reason=f'Inventory reservation rejected: {reason}',
            )
            return {'order_id': str(order_id), 'status': OrderStatus.CANCELLED}



        elif event_type == 'payment.succeeded':
            OrderService.transition_order_status(
                order_id=order_id,
                to_status=OrderStatus.PAID,
                reason=f"Payment succeeded (tx: {payload.get('provider_tx_id', 'N/A')}).",
            )
            return {'order_id': str(order_id), 'status': OrderStatus.PAID}



        elif event_type == 'payment.failed':
            reason = str(payload.get('reason', 'PAYMENT_DECLINED'))
            OrderService.transition_order_status(
                order_id=order_id,
                to_status=OrderStatus.CANCELLED,
                reason=f'Payment failed: {reason}',
            )
            return {'order_id': str(order_id), 'status': OrderStatus.CANCELLED}


        raise PermanentProcessingError(f'Unsupported event_type: {event_type}')



    @staticmethod
    def _get_required_str(data: Mapping[str, object], field_name: str) -> str:
        value = data.get(field_name)

        if not isinstance(value, str) or not value.strip():
            raise InvalidEventError(f'Missing or blank required field: {field_name}')

        return value.strip()

