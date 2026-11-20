from django.contrib import admin
from catalog.models import (
    Brand,
    Category,
    Inventory,
    InventoryReservation,
    Product,
    ProductVariant,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'parent', 'is_active']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'category', 'brand', 'base_price', 'is_active', 'created_at']
    list_filter = ['is_active', 'category', 'brand']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ['sku', 'product', 'price_override', 'is_active']
    search_fields = ['sku', 'product__name']


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['variant', 'total_quantity', 'reserved_quantity', 'updated_at']


@admin.register(InventoryReservation)
class InventoryReservationAdmin(admin.ModelAdmin):
    list_display = ['order_id', 'variant', 'quantity', 'status', 'created_at']
    list_filter = ['status']