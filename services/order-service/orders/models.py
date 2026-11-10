import uuid
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from orders.state_machine import OrderStatus


class Order(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user_id = models.UUIDField(db_index=True)
    idempotency_key = models.CharField(max_length=120, unique=True, db_index=True)
    status = models.CharField(max_length=30, choices=OrderStatus.CHOICES, default=OrderStatus.PENDING, db_index=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    currency = models.CharField(max_length=10, default='USD')
    shipping_address = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user_id', '-created_at'], name='idx_orders_user_created'),
            models.Index(fields=['status', '-created_at'], name='idx_orders_status_created'),
        ]

    def __str__(self) -> str:
        return f'Order {self.id} ({self.status}) - {self.total_amount} {self.currency}'



class OrderItem(models.Model):
    """
    Stores an immutable snapshot of product variant details (product_name, sku, unit_price)
    at the moment the order was placed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant_id = models.UUIDField(db_index=True)
    product_name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])

    class Meta:
        db_table = 'order_items'

    def __str__(self) -> str:
        return f'{self.sku} x {self.quantity} ({self.subtotal})'



class OrderStatusHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_status_history'
        ordering = ['created_at']

    def __str__(self) -> str:
        return f'Order {self.order_id}: {self.from_status} -> {self.to_status}'