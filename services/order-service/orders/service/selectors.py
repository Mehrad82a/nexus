from typing import Optional
from uuid import UUID
from django.db.models import QuerySet
from orders.models import Order



def get_user_orders(*, user_id: UUID) -> QuerySet[Order]:
    """
        Fetch user orders with prefetched items and status history to prevent N+1 queries.
        """
    return (
        Order.objects.filter(user_id=user_id)
        .prefetch_related("items", "status_history")
        .order_by("-created_at")
    )



def get_order_by_id(*, order_id: UUID, user_id: Optional[UUID] = None) -> Optional[Order]:
    queryset = Order.objects.filter(id=order_id).prefetch_related('items', 'status_history')
    if user_id is not None:
        queryset = queryset.filter(user_id=user_id)

    return queryset.first()




