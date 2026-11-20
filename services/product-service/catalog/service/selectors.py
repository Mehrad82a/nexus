from typing import Optional
from uuid import UUID
from django.core.cache import cache
from django.db.models import Prefetch, QuerySet
from catalog.models import Brand, Category, Product, ProductVariant


PRODUCT_DETAIL_CACHE_TTL = 60 * 15  # 15 minutes


def get_product_cache_key(slug: str) -> str:
    return f'nexus:product:detail:{slug}'



def invalidate_product_cache(slug: str) -> None:
    cache.delete(get_product_cache_key(slug))


def get_active_categories() -> QuerySet[Category]:
    return Category.objects.filter(is_active=True).select_related('parent')


def get_all_brands() -> QuerySet[Brand]:
    return Brand.objects.all()



def get_optimized_product_list(
    *,
    category_slug: Optional[str] = None,
    brand_slug: Optional[str] = None,
    search: Optional[str] = None,
) -> QuerySet[Product]:

    active_variants_prefetch = Prefetch(
        'variants',
        queryset=ProductVariant.objects.filter(is_active=True).select_related('inventory'),
    )

    queryset = (
        Product.objects.filter(is_active=True)
        .select_related('category', 'brand')
        .prefetch_related(active_variants_prefetch)
    )

    if category_slug:
        queryset = queryset.filter(category__slug=category_slug)

    if brand_slug:
        queryset = queryset.filter(brand__slug=brand_slug)

    if search:
        queryset = queryset.filter(name__icontains=search.strip())

    return queryset



def get_product_by_slug(*, slug: str) -> Optional[Product]:
    active_variants_prefetch = Prefetch(
        'variants',
        queryset=ProductVariant.objects.filter(is_active=True).select_related('inventory'),
    )

    return (
        Product.objects.filter(slug=slug, is_active=True)
        .select_related('category', 'brand')
        .prefetch_related(active_variants_prefetch)
        .first()
    )



def get_variant_with_inventory(*, variant_id: UUID) -> Optional[ProductVariant]:
    return (
        ProductVariant.objects.filter(id=variant_id, is_active=True)
        .select_related('product', 'inventory')
        .first()
    )