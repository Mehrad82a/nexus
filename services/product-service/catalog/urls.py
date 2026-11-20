from django.urls import path
from catalog.views import (
    BrandListCreateAPIView,
    CategoryListCreateAPIView,
    InternalReserveStockAPIView,
    ProductDetailAPIView,
    ProductListCreateAPIView,
    VariantSnapshotAPIView,
)


app_name = 'catalog'

urlpatterns = [
    path('categories/', CategoryListCreateAPIView.as_view(), name='category_list_create'),
    path('brands/', BrandListCreateAPIView.as_view(), name='brand_list_create'),
    path('products/', ProductListCreateAPIView.as_view(), name='product_list_create'),
    path('products/<slug:slug>/', ProductDetailAPIView.as_view(), name='product_detail'),
    path('variants/<uuid:variant_id>/snapshot/', VariantSnapshotAPIView.as_view(), name='variant_snapshot'),
    path('inventory/reserve/', InternalReserveStockAPIView.as_view(), name='inventory_reserve'),
]
