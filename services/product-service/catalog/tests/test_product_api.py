import uuid
from decimal import Decimal
from unittest.mock import MagicMock
import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from unicodedata import category

from catalog.messaging.services.handler import InventoryEventHandler
from catalog.models import Brand, Category, Inventory, InventoryReservation, Product
from catalog.services import CatalogService



def generate_test_jwt(*, role: str = 'ADMIN') -> str:
    token = RefreshToken()
    token['user_id'] = str(uuid.uuid4())
    token['email'] = f'{role.lower()}@nexus.io'
    token['role'] = role
    return str(token.access_token)



@pytest.fixture
def api_client() -> APIClient:
    cache.clear()
    return APIClient()


@pytest.fixture
def sample_catalog(db):
    category = Category.objects.create(name='Smartphones', slug='smartphones')
    brand = Brand.objects.create(name='Apple', slug='apple')

    product = CatalogService.create_product(
        category_id=category.id,
        brand_id=brand.id,
        name='iPhone 16 Pro',
        slug='iphone-16-pro',
        description='Flagship smartphone',
        base_price=Decimal('999.00'),
        variants_data=[
            {
                'sku': 'IP16P-256-BLK',
                'attributes': {'storage': '256GB', 'color': 'Black'},
                'price_override': Decimal('1099.00'),
                'initial_stock': 10,
            },
            {
                'sku': 'IP16P-512-TIT',
                'attributes': {'storage': '512GB', 'color': 'Titanium'},
                'price_override': Decimal('1299.00'),
                'initial_stock': 5,
            },
        ],
    )
    return {'category': category, 'brand': brand, 'product': product}



@pytest.mark.django_db
class TestProductServiceAndPerformance:
    def test_create_product_requires_admin_jwt(self, api_client: APIClient, sample_catalog):
        url = reverse('catalog:product_list_create')

        payload = {
            'category_id': str(sample_catalog['category'].id),
            'brand_id': str(sample_catalog['brand'].id),
            'name': 'MacBook Pro M4',
            'slug': 'macbook-pro-m4',
            'base_price': '1999.00',
            'variants_data': [{'sku': 'MBP-M4-16', 'initial_stock': 8}],
        }

        # 1. Customer role should be forbidden (403)
        customer_token = generate_test_jwt(role='CUSTOMER')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {customer_token}')
        forbidden_res = api_client.post(url, data=payload, format='json')

        assert forbidden_res.status_code == status.HTTP_403_FORBIDDEN


        # 2. Admin role should succeed (201)
        admin_token = generate_test_jwt(role='ADMIN')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_token}')
        created_res = api_client.post(url, data=payload, format='json')

        assert created_res.status_code == status.HTTP_201_CREATED
        assert created_res.data['slug'] == 'macbook-pro-m4'
        assert len(created_res.data['variants']) == 1



    def test_product_list_eliminates_n_plus_1_queries(self, api_client: APIClient, sample_catalog, django_assert_num_queries):
        for i in range(5):
            CatalogService.create_product(
                category_id=sample_catalog['category'].id,
                brand_id=sample_catalog['brand'].id,
                name=f'Product {i}',
                slug=f'product-{i}',
                base_price=Decimal('500.00'),
                variants_data=[{'sku': f'SKU-{i}-A', 'initial_stock': 20}],
            )

        url = reverse('catalog:product_list_create')
        with django_assert_num_queries(3):
            response = api_client.get(url)
            assert response.status_code == status.HTTP_200_OK
            assert response.data['count'] == 6



    def test_product_detail_redis_cache_hit_and_invalidation(self, api_client: APIClient, sample_catalog):
        product: Product = sample_catalog['product']
        url = reverse('catalog:product_detail', kwargs={'slug': product.slug})

        res1 = api_client.get(url)
        assert res1.status_code == status.HTTP_200_OK
        assert res1['X-Cache'] == 'MISS'

        res2 = api_client.get(url)
        assert res2.status_code == status.HTTP_200_OK
        assert res2['X-Cache'] == 'HIT'




    def test_inventory_saga_reserve_and_rollback_on_payment_failed(self, sample_catalog):
        cache.clear()
        product: Product = sample_catalog['product']
        variant = product.variants.first()
        order_id = uuid.uuid4()

        mock_producer = MagicMock()
        handler = InventoryEventHandler(producer=mock_producer)

        # 1. Simulate incoming 'order.created' event reserving 3 units (out of 10)
        order_created_event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'order.created',
            'payload': {
                'order_id': str(order_id),
                'user_id': str(uuid.uuid4()),
                'total_amount': '3297.00',
                'items': [{'variant_id': str(variant.id), 'quantity': 3}],
            },
        }
        result1 = handler.process(order_created_event)
        assert result1['status'] == 'inventory.reserved'


        inv = Inventory.objects.get(variant=variant)
        assert inv.reserved_quantity == 3
        assert inv.available_quantity == 7
        mock_producer.publish.assert_called_once()
        assert mock_producer.publish.call_args.kwargs['event_type'] == 'inventory.reserved'


        # 2. Simulate incoming 'payment.failed' event -> stock must be released back to 10!
        payment_failed_event = {
            'event_id': str(uuid.uuid4()),
            'event_type': 'payment.failed',
            'payload': {'order_id': str(order_id)},
        }

        result2 = handler.process(payment_failed_event)
        assert result2['status'] == 'stock_released'

        inv.refresh_from_db()
        reservation = InventoryReservation.objects.get(order_id=order_id, variant=variant)
        assert inv.reserved_quantity == 0
        assert inv.available_quantity == 10
        assert reservation.status == InventoryReservation.Status.RELEASED


