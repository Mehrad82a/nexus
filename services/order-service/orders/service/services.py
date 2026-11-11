from decimal import Decimal
from typing import Any, Dict, List
from uuid import UUID
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from orders.service.locks import redis_distributed_lock
from orders.messaging.producer.producer import EventProducer
from orders.models import Order, OrderItem, OrderStatusHistory
from orders.state_machine import (
    InvalidOrderStateTransitionError,
    OrderStateMachine,
    OrderStatus,
)


class OrderService:
    """
    Application Service Layer orchestrating order creation, Redis distributed locking,
    state machine transitions, and RabbitMQ Saga event publishing.
    """

    @staticmethod
    def create_order(
        *,
        user_id: UUID,
        idempotency_key: str,
        currency: str = 'USD',
        shipping_address: Dict[str, Any],
        items_data: List[Dict[str, Any]],
        producer: EventProducer | None = None,
    ) -> Order:

        cleaned_key = idempotency_key.strip()
        if not cleaned_key:
            raise ValidationError({'idempotency_key': 'Idempotency key cannot be blank.'})

        # Acquire Redis Distributed Lock per user + idempotency key to prevent race conditions
        with redis_distributed_lock(f'{user_id}:{cleaned_key}', ttl_seconds=15):
            existing = (
                Order.objects.filter(idempotency_key=cleaned_key)
                .prefetch_related('items', 'status_history')
                .first()
            )

            if existing:
                return existing

            event_producer = producer if producer is not None else EventProducer()

            with transaction.atomic():
                total_amount = Decimal('0.00')
                order = Order.objects.create(
                    user_id=user_id,
                    idempotency_key=cleaned_key,
                    status=OrderStatus.PENDING,
                    currency=currency,
                    shipping_address=shipping_address,
                )

                order_items: List[OrderItem] = []
                saga_items_payload: List[Dict[str, Any]] = []

                for item in items_data:
                    qty = int(item['quantity'])
                    unit_price = Decimal(str(item['unit_price']))
                    subtotal = unit_price * qty
                    total_amount += subtotal

                    order_items.append(
                        OrderItem(
                            order=order,
                            variant_id=item['variant_id'],
                            product_name=item['product_name'],
                            sku=item['sku'],
                            quantity=qty,
                            unit_price=unit_price,
                            subtotal=subtotal,
                        )
                    )

                    saga_items_payload.append(
                        {
                            'variant_id': str(item['variant_id']),
                            'quantity': qty,
                        }
                    )

                OrderItem.objects.bulk_create(order_items)

                order.total_amount = total_amount
                order.save(update_fields=['total_amount', 'updated_at'])

                OrderStatusHistory.objects.create(
                    order=order,
                    from_status='',
                    to_status=OrderStatus.PENDING,
                    reason='Order created by customer.',
                )

            # Publish Saga starter event to RabbitMQ
            event_producer.publish(
                event_type='order.created',
                payload={
                    'order_id': str(order.id),
                    'user_id': str(order.user_id),
                    'total_amount': str(order.total_amount),
                    'currency': order.currency,
                    'items': saga_items_payload,
                },
            )

            return order



    @staticmethod
    @transaction.atomic()
    def transition_order_status(
        *,
        order_id: UUID,
        to_status: str,
        reason: str = '',
    ) -> Order:
        order = Order.objects.select_for_update().filter(id=order_id).first()
        if not order:
            raise NotFound(f'Order {order_id} not found.')

        if order.status == to_status:
            return order


        try:
            OrderStateMachine.validate_transition(from_status=order.status, to_status=to_status)

        except InvalidOrderStateTransitionError as exc:
            raise ValidationError({'status': str(exc)}) from exc


        previous_status = order.status
        order.status = to_status
        order.save(update_fields=['status', 'updated_at'])

        OrderStatusHistory.objects.create(
            order=order,
            from_status=previous_status,
            to_status=to_status,
            reason=reason,
        )

        return order


    @classmethod
    def cancel_order_by_customer(
        cls,
        *,
        order_id: UUID,
        user_id: UUID,
        reason: str = 'Cancelled by customer.',
        producer: EventProducer | None = None,
    ) -> Order:

        with redis_distributed_lock(f'cancel:{order_id}', ttl_seconds=10):
            order = Order.objects.filter(id=order_id, user_id=user_id).first()
            if not order:
                raise NotFound(f'Order not found.')


            if not OrderStateMachine.can_consumer_cancel(current_status=order.status):
                raise ValidationError({'detail': f'Order in <{order.status}> status cannot be cancelled.'})


            updated_order = cls.transition_order_status(
                order_id=order_id,
                to_status=OrderStatus.CANCELLED,
                reason=reason,
            )

            event_producer = producer if producer is not None else EventProducer()
            event_producer.publish(
                event_type='order.cancelled',
                payload={
                    'order_id': str(updated_order.id),
                    'user_id': str(updated_order.user_id),
                    'reason': reason,
                },
            )
            return updated_order



