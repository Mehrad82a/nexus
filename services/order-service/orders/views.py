from uuid import UUID
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from orders.service.selectors import get_order_by_id, get_user_orders
from orders.serializers import (
    OrderCancelInputSerializer,
    OrderCreateInputSerializer,
    OrderOutputSerializer,
)
from orders.service.services import OrderService




class OrderListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = OrderOutputSerializer

    def get_queryset(self):
        return get_user_orders(user_id=UUID(str(self.request.user.id)))

    def create(self, request: Request, *args, **kwargs) -> Response:
        data = request.data.cop() if isinstance(request.data, dict) else {}
        header_key = request.headers.get('Idempotency-Key')
        if header_key and 'idempotency_key' not in data:
            data['idempotency_key'] = header_key


        serializer = OrderCreateInputSerializer(data=data)
        serializer.is_valid(raise_exception=True)

        order = OrderService.create_order(
            user_id=UUID(str(request.user.id)),
            **serializer.validated_data
        )
        refetched = get_order_by_id(order_id=order.id)

        return Response(
            OrderOutputSerializer(refetched).data,
            status=status.HTTP_201_CREATED
        )




class OrderDetailAPIView(APIView):
    def get(self, request: Response, order_id: UUID) -> Response:
        order = get_order_by_id(order_id=order_id, user_id=UUID(str(request.user.id)))
        if not order:
            return Response({'detail': 'Order not found.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(OrderOutputSerializer(order).data, status=status.HTTP_200_OK)



class OrderCancelAPIView(APIView):
    def post(self, request: Request, order_id: UUID) -> Response:
        serializer = OrderCancelInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = OrderService.cancel_order_by_customer(
            order_id=order_id,
            user_id=UUID(str(request.user.id)),
            reason=serializer.validated_data["reason"],
        )
        refetched = get_order_by_id(order_id=order.id)

        return Response(OrderOutputSerializer(refetched).data, status=status.HTTP_200_OK)

