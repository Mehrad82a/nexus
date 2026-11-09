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
from catalog.service.selectors import invalidate_product_cache




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




class InventoryService:
    """
    Handles concurrency-safe stock reservations, confirmations, and rollbacks
    using PostgreSQL row-level locking (SELECT ... FOR UPDATE).
    """

    @staticmethod
    @transaction.atomic
    def reserve_stock_for_order(
        *,
        order_id: UUID,
        items: List[Dict[str, Any]],
    ) -> List[InventoryReservation]:
        """
        Reserves stock for all items in an order.
        """

        existing = list(InventoryReservation.objects.filter(order_id=order_id))
        if existing:
            return existing

        variant_ids = sorted([UUID(str(item['variant_id'])) for item in items])

        inventories = {
            inv.variant_id: inv for inv in Inventory.objects.select_for_update()
            .select_related('variant__product')
            .filter(variant_id__in=variant_ids)
        }

        reservations: List[InventoryReservation] = []

        for item in items:
            v_id = UUID(str(item['variant_id']))
            qty = int(item['quantity'])

            inventory: Optional[Inventory] = inventories.get(v_id)
            if not inventory:
                raise NotFound(f'Inventory for variant {v_id} not found.')

            if inventory.available_quantity < qty:
                raise ValidationError(
                    {
                        'detail': 'INSUFFICIENT_STOCK',
                        'variant_id': str(v_id),
                        'available': inventory.available_quantity,
                        'requested': qty,
                    }
                )

            inventory.reserved_quantity += qty
            inventory.save(update_fields=['reserved_quantity', 'updated_at'])

            reservation = InventoryReservation.objects.create(
                order_id=order_id,
                variant_id=v_id,
                quantity=qty,
                status=InventoryReservation.Status.RESERVED,
            )

            reservations.append(reservation)
            invalidate_product_cache(inventory.variant.product.slug)

        return reservations



    @staticmethod
    @transaction.atomic
    def confirm_order_stock(*, order_id: UUID) -> None:
        """
        Called when payment.succeeded event arrives: permanently deducts stock.
        """

        reservations = list(
            InventoryReservation.objects.select_for_update()
            .select_related('variant__product')
            .filter(order_id=order_id, status=InventoryReservation.Status.RESERVED)
        )

        for res in reservations:
            inv = Inventory.objects.select_for_update().get(variant_id=res.variant_id)
            inv.total_quantity = max(0, inv.total_quantity - res.quantity)
            inv.reserved_quantity = max(0, inv.reserved_quantity - res.quantity)
            inv.save(update_fields=['total_quantity', 'reserved_quantity', 'updated_at'])

            res.status = InventoryReservation.Status.CONFIRMED
            res.save(update_fields=['status'])
            invalidate_product_cache(res.variant.product.slug)



    @staticmethod
    @transaction.atomic
    def release_order_stock(*, order_id: UUID) -> None:
        """
        Called when payment.failed or order.cancelled event arrives: releases reserved stock.
        """

        reservations = list(
            InventoryReservation.objects.select_for_update()
            .select_related('variant__product')
            .filter(order_id=order_id, status=InventoryReservation.Status.RESERVED)

        )

        for res in reservations:
            inv = Inventory.objects.select_for_update().get(variant_id=res.variant_id)
            inv.reserved_quantity = max(0, inv.reserved_quantity - res.quantity)
            inv.save(update_fields=['reserved_quantity', 'updated_at'])

            res.status = InventoryReservation.Status.RELEASED
            res.save(update_fields=['status'])
            invalidate_product_cache(res.variant.product.slug)






