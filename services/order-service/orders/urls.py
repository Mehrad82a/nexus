from django.urls import path
from orders.views import (
    OrderCancelAPIView,
    OrderDetailAPIView,
    OrderListCreateAPIView,
)

app_name = 'orders'

urlpatterns = [
    path('', OrderListCreateAPIView.as_view(), name='order_list_create'),
    path('<uuid:order_id>/', OrderDetailAPIView.as_view(), name='order_detail'),
    path('<uuid:order_id>/cancel/', OrderCancelAPIView.as_view(), name='order_cancel'),
]

