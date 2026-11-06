from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID
from django.db import transaction
from rest_framework.exceptions import NotFound, ValidationError

from catalog.models import (
    Brand,
    Category,
    Inventory,
    InventoryReservation,
    Product,
    ProductVariant,
)
from catalog.selectors import invalidate_product_cache




class CatalogService:
    """
    Service layer handling product creation, variant setup, and cache invalidation.
    """

    @staticmethod
    @transaction.atomic
    def create_product(
        *,
        category_id: UUID,
        brand_id: UUID,
        name: str,
        slug: str,
        description: str = '',
        base_price: Decimal,
        variants_data: List[Dict[str, Any]],
    ) -> Product:

        category = Category.objects.filter(id=category_id, is_active=True).first()
        if not category:
            raise ValidationError({'category_id': 'Active category not found.'})


        brand = Brand.objects.filter(id=brand_id).first()
        if not brand:
            raise ValidationError({'brand_id': 'Brand not found.'})


        if Product.objects.filter(slug=slug).exists():
            raise ValidationError({'slug': 'Product with this slug already exists.'})


        product = Product.objects.create(
            category=category,
            brand=brand,
            name=name,
            slug=slug,
            description=description,
            base_price=base_price,
        )

        for v_data in variants_data:
            variant = ProductVariant.objects.create(
                product=product,
                sku=v_data['sku'],
                attributes=v_data.get('attributes', {}),
                price_override=v_data.get('price_override'),
            )

            Inventory.objects.create(
                variant=variant,
                total_quantity=v_data.get('initial_stock', 0),
                reserved_quantity=0,
            )

        invalidate_product_cache(product.slug)
        return product

