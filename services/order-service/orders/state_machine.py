from typing import Dict, Set



class InvalidOrderStateTransitionError(Exception):
    """Raised when an invalid state transition is attempted on an Order."""


class OrderStatus:
    PENDING = 'PENDING'
    INVENTORY_RESERVED = 'INVENTORY_RESERVED'
    PAYMENT_PENDING = 'PAYMENT_PENDING'
    PAID = 'PAID'
    PROCESSING = 'PROCESSING'
    SHIPPED = 'SHIPPED'
    DELIVERED = 'DELIVERED'
    CANCELLED = 'CANCELLED'

    CHOICES = [
        (PENDING, 'Pending'),
        (INVENTORY_RESERVED, 'Inventory Reserved'),
        (PAYMENT_PENDING, 'Payment Pending'),
        (PAID, 'Paid'),
        (PROCESSING, 'Processing'),
        (SHIPPED, 'Shipped'),
        (DELIVERED, 'Delivered'),
        (CANCELLED, 'Cancelled'),
    ]



class OrderStateMachine:
    """
    Defines the deterministic finite state machine (FSM) for NEXUS orders.
    """

    ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
        OrderStatus.PENDING: {
            OrderStatus.INVENTORY_RESERVED,
            OrderStatus.PAYMENT_PENDING,
            OrderStatus.CANCELLED,
        },

        OrderStatus.INVENTORY_RESERVED: {
            OrderStatus.PAYMENT_PENDING,
            OrderStatus.PAID,
            OrderStatus.CANCELLED,
        },

        OrderStatus.PAYMENT_PENDING: {
            OrderStatus.PAID,
            OrderStatus.CANCELLED,
        },

        OrderStatus.PAID: {
            OrderStatus.PROCESSING,
            OrderStatus.SHIPPED,
            OrderStatus.CANCELLED,
        },

        OrderStatus.PROCESSING: {
            OrderStatus.SHIPPED,
            OrderStatus.CANCELLED,
        },

        OrderStatus.SHIPPED: {
            OrderStatus.DELIVERED,
        },

        OrderStatus.DELIVERED: set(),
        OrderStatus.CANCELLED: set(),
    }


    CANCELLABLE_STATES: Set[str] = {
        OrderStatus.PENDING,
        OrderStatus.INVENTORY_RESERVED,
        OrderStatus.PAYMENT_PENDING,
    }


    @classmethod
    def can_transition(cls, *, from_status: str, to_status: str) -> bool:
        allowed = cls.ALLOWED_TRANSITIONS.get(from_status, set())
        return to_status in allowed


    @classmethod
    def validate_transition(cls, *, from_status: str, to_status: str) -> None:
        if from_status == to_status:
            return

        if not cls.can_transition(from_status=from_status, to_status=to_status):
            raise InvalidOrderStateTransitionError(f'Cannot transition order from <{from_status}> to <{to_status}>.')


    @classmethod
    def can_consumer_cancel(cls, *, current_status: str) -> bool:
        return current_status in cls.CANCELLABLE_STATES


