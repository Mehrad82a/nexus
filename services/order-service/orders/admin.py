from django.contrib import admin
from orders.models import Order, OrderItem, OrderStatusHistory




class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['variant_id', 'product_name', 'sku', 'quantity', 'unit_price', 'subtotal']



class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ['from_status', 'to_status', 'reason', 'created_at']



@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user_id', 'status', 'total_amount', 'currency', 'created_at']
    list_filter = ['status', 'currency']
    search_fields = ['id', 'user_id', 'idempotency_key']
    inlines = [OrderItemInline, OrderStatusHistoryInline]