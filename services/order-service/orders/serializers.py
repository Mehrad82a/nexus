from decimal import Decimal
from rest_framework import serializers
from orders.models import Order, OrderItem, OrderStatusHistory




class OrderItemOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'variant_id', 'product_name', 'sku', 'quantity', 'unit_price', 'subtotal']



class OrderStatusHistoryOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderStatusHistory
        fields = ['id', 'from_status', 'to_status', 'reason', 'created_at']



class OrderOutputSerializer(serializers.ModelSerializer):
    items = OrderItemOutputSerializer(many=True, read_only=True)
    status_history = OrderStatusHistoryOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user_id', 'idempotency_key', 'status', 'total_amount', 'currency', 'shipping_address', 'items', 'status_history', 'created_at', 'updated_at']




class OrderItemCreateInputSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    product_name = serializers.CharField(max_length=255)
    sku = serializers.CharField(max_length=100)
    quantity = serializers.IntegerField(min_value=1)
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.00'))



class OrderCreateInputSerializer(serializers.Serializer):
    idempotency_key = serializers.CharField(max_length=120)
    currency = serializers.CharField(max_length=10, default='USD')
    shipping_address = serializers.DictField()
    items_data = OrderItemCreateInputSerializer(many=True, min_length=1)



class OrderCancelInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, default='Cancelled by customer.')

