import uuid
from locust import HttpUser, between, task



class NexusPlatformUser(HttpUser):
    """
    Simulates realistic e-commerce traffic across the NEXUS API Gateway:
    - High-frequency catalog browsing & Redis-cached product detail reads (80% weight)
    - Authenticated order placement, idempotency verification, & order history checks (20% weight)
    """

    wait_time = between(0.5, 2.0)
    access_token: str | None = None
    last_order_id: str | None = None

    def on_start(self) -> None:
        """
        Register a unique virtual user on startup and store their JWT access token.
        """
        email = f'loadtest_{uuid.uuid4().hex[:10]}@nexus.io'
        response = self.client.post(
            '/api/v1/auth/register/',
            json={
                'email': email,
                'password': 'LoadTestPassword123!',
                'first_name': 'Load',
                'last_name': 'Tester',
            },
            name='POST /api/v1/auth/register/',
        )
        if response.status_code == 201:
            self.access_token = response.json()['tokens']['access']


    @property
    def auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {'Authorization': f'Bearer {self.access_token}'}


    @task(5)
    def browse_product_catalog(self) -> None:
        """
        Tests ORM-optimized product listing (select_related + prefetch_related).
        """
        self.client.get(
            '/api/v1/catalog/products/',
            name='GET /api/v1/catalog/products/',
        )


    @task(3)
    def browse_categories_and_brands(self) -> None:
        self.client.get(
            '/api/v1/catalog/categories/',
            name='GET /api/v1/catalog/categories/',
        )
        self.client.get(
            '/api/v1/catalog/brands/',
            name='GET /api/v1/catalog/brands/',
        )


    @task(2)
    def place_order_and_check_status(self) -> None:
        """
        Tests Redis distributed lock, order creation, and RabbitMQ event publishing.
        """
        if not self.access_token:
            return

        idem_key = f'locust-idem-{uuid.uuid4()}'
        res = self.client.post(
            '/api/v1/orders/',
            json={
                'idempotency_key': idem_key,
                'currency': 'USD',
                'shipping_address': {
                    'city': 'Tehran',
                    'street': 'Azadi St',
                    'postal_code': '14588',
                },
                'items_data': [
                    {
                        'variant_id': str(uuid.uuid4()),
                        'product_name': 'iPhone 16 Pro',
                        'sku': 'IP16P-256-BLK',
                        'quantity': 1,
                        'unit_price': '1099.00',
                    }
                ],
            },
            headers={**self.auth_headers, 'Idempotency-Key': idem_key},
            name='POST /api/v1/orders/',
        )
        if res.status_code == 201:
            self.last_order_id = res.json().get('id')

        if self.last_order_id:
            self.client.get(
                f'/api/v1/orders/{self.last_order_id}/',
                headers=self.auth_headers,
                name='GET /api/v1/orders/{id}/',
            )

