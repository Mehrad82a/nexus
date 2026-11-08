import uuid
from collections.abc import Mapping
from django.core.cache import cache
from django.db import OperationalError
from rest_framework.exceptions import NotFound, ValidationError

from catalog.messaging.services.exceptions import (
    InvalidEventError,
    PermanentProcessingError,
    TransientProcessingError,
)
from catalog.messaging.core.logger import get_logger
from catalog.messaging.producer.producer import EventProducer
from catalog.services import InventoryService


logger = get_logger(__name__)



class InventoryEventHandler:
    """
    Validate incoming Saga events, enforce Redis idempotency, execute InventoryService
    operations, and classify failures into Transient vs. Permanent for the Consumer.
    """

    def __init__(self, *, producer: EventProducer | None = None) -> None:
        self._producer = producer if producer is not None else EventProducer()


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


        dedup_key = f'nexus:product:processed_event:{event_id}'
        if cache.get(dedup_key):
            logger.info(f'[InventoryEventHandler] Duplicate event skipped: event_id=<{event_id}>')
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

        except NotFound as exc:
            raise PermanentProcessingError(f'Referenced entity not found: {exc}') from exc


        cache.set(dedup_key, '1', timeout=60 * 60 * 24)
        return result


    def _dispatch(
        self,
        *,
        event_type: str,
        order_id: uuid.UUID,
        payload: dict[str, object],
    ) -> dict[str, object]:

        if event_type == 'order.created':
            items = payload.get('items')

            if not isinstance(items, list) or not items:
                raise PermanentProcessingError('order.created payload must contain a non-empty items list.')


            try:
                reservations = InventoryService.reserve_stock_for_order(
                    order_id=order_id,
                    items=items,
                )

                self._producer.publish(
                    event_type='inventory.reserved',
                    payload={
                        'order_id': str(order_id),
                        'user_id': payload.get('user_id'),
                        'total_amount': payload.get('total_amount'),
                        'currency': payload.get('currency', 'USD'),
                        'reservation_id': str(reservations[0].id) if reservations else None,
                    }
                )
                return {
                    'order_id': str(order_id),
                    'status': 'inventory.reserved'
                }


            except ValidationError as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {}

                self._producer.publish(
                    event_type='inventory.rejected',
                    payload={
                        'order_id': str(order_id),
                        'reason': detail.get('detail', 'INSUFFICIENT_STOCK'),
                        'failed_variant_id': detail.get('variant_id'),
                    },
                )

                return {
                    'order_id': str(order_id),
                    'status': 'inventory.rejected',
                }


        elif event_type == 'payment.succeeded':
            InventoryService.confirm_order_stock(order_id=order_id)
            return {
                'order_id': str(order_id),
                'status': 'stock_confirmed',
            }

        elif event_type in ('payment.failed', 'order.cancelled'):
            InventoryService.release_order_stock(order_id=order_id)
            return {
                'order_id': str(order_id),
                'status': 'stock_released',
            }

        raise PermanentProcessingError(f'Unsupported event_type: {event_type}')




    @staticmethod
    def _get_required_str(data: Mapping[str, object], field_name: str) -> str:
        value = data.get(field_name)

        if not isinstance(value, str) or not value.strip():
            raise InvalidEventError(f'Missing or blank required field: {field_name}')

        return value.strip()

