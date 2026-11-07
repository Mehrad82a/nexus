from http.client import responses

from django.core.cache import cache
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.selectors import (
    PRODUCT_DETAIL_CACHE_TTL,
    get_active_categories,
    get_all_brands,
    get_optimized_product_list,
    get_product_by_slug,
    get_product_cache_key,
    get_variant_with_inventory,
)
from catalog.serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductCreateInputSerializer,
    ProductOutputSerializer,
    ReserveStockInputSerializer,
)
from catalog.services import CatalogService, InventoryService




class CategoryListCreateAPIView(generics.ListCreateAPIView):
    queryset = get_active_categories()
    serializer_class = CategorySerializer


class BrandListCreateAPIView(generics.ListCreateAPIView):
    queryset = get_all_brands()
    serializer_class = BrandSerializer


class ProductListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = ProductOutputSerializer

    def get_queryset(self):
        return get_optimized_product_list(
            category_slug=self.request.query_params.get('category'),
            brand_slug=self.request.query_params.get('brand'),
            search=self.request.query_params.get('search'),
        )


    def create(self, request, *args, **kwargs) -> Response:
        input_serializer = ProductCreateInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        product = CatalogService.create_product(**input_serializer.validated_data)
        refetched = get_product_by_slug(slug=product.slug)

        return Response(
            ProductOutputSerializer(refetched).data,
            status=status.HTTP_201_CREATED,
        )



class ProductDetailAPIView(APIView):
    """
    Demonstrates Redis read-through caching (<15ms response on cache hit).
    """

    def get(self, request: Request, slug: str) -> Response:
        cache_key = get_product_cache_key(slug)
        cached_data = cache.get(cache_key)

        if cached_data is not None:
            response = Response(cached_data, status=status.HTTP_200_OK)
            response['X-Cache'] = 'HIT'
            return response

        product = get_product_by_slug(slug=slug)
        if not product:
            return Response(
                {
                    'detail': 'Product not found',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serialized_data = ProductOutputSerializer(product).data
        cache.set(cache_key, serialized_data, timeout=PRODUCT_DETAIL_CACHE_TTL)

        response = Response(serialized_data, status=status.HTTP_200_OK)
        response['X-Cache'] = 'MISS'
        return response





class VariantSnapshotAPIView(APIView):
    """
    Internal endpoint used by order-service to fetch variant snapshot & price.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, variant_id) -> Response:
        variant = get_variant_with_inventory(variant_id=variant_id)

        if not variant_id:
            return Response(
                {
                    'detail': 'Variant not found',
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        return Response(
            {
                'variant_id': str(variant.id),
                'product_id': str(variant.product_id),
                'product_name': variant.product.name,
                'sku': variant.sku,
                'unit_price': str(variant.effective_price),
                'available_quantity': variant.inventory.available_quantity,
            },
            status=status.HTTP_200_OK,
        )




class InternalReserveStockAPIView(APIView):
    """
    Endpoint to atomically reserve stock for an order.
    """

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        serializer = ReserveStockInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reservations = InventoryService.reserve_stock_for_order(**serializer.validated_data)

        return Response(
            {
                'order_id': str(serializer.validated_data['order_id']),
                'status': 'RESERVED',
                'reserved_items': len(reservations),
            },
            status=status.HTTP_200_OK,
        )