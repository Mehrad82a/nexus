import uuid
from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models





class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True, db_index=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True, db_index=True)


    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return f'{self.id} --- {self.name}'




class Brand(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True, db_index=True)

    class Meta:
        db_table = 'brands'
        ordering = ['name']

    def __str__(self):
        return f'{self.id} --- {self.name}'



class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='products')

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True)
    base_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', '-created_at'], name='idx_prod_active_created'),
            models.Index(fields=['category', 'is_active'], name='idx_prod_category_active'),
            models.Index(fields=['brand', 'is_active'], name='idx_prod_brand_active'),
        ]


    def __str__(self):
        return f'{self.id} --- {self.name}'




class ProductVariant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')

    sku = models.CharField(max_length=100, unique=True, db_index=True)
    attributes = models.JSONField(default=dict, blank=True)
    price_override = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.00'))])

    is_active = models.BooleanField(default=True, db_index=True)


    class Meta:
        db_table = 'product_variants'
        indexes = [
            models.Index(fields=['product', 'is_active'], name='idx_variant_prod_active'),
        ]

    @property
    def effective_price(self) -> Decimal:
        return self.price_override if self.price_override is not None else self.product.base_price

    def __str__(self):
        return f'{self.id} - {self.product.name} - {self.sku}'




class Inventory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    variant = models.OneToOneField(ProductVariant, on_delete=models.CASCADE, related_name='inventory')

    total_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory'
        verbose_name_plural = 'inventories'


    @property
    def available_quantity(self) -> int:
        return max(0, self.total_quantity - self.reserved_quantity)

    def __str__(self) -> str:
        return f'{self.variant.sku}: {self.available_quantity} available'




class InventoryReservation(models.Model):
    class Status(models.TextChoices):
        RESERVED = 'RESERVED', 'Reserved'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        RELEASED = 'RELEASED', 'Released'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = models.UUIDField(db_index=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name='reservations')

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RESERVED, db_index=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        db_table = 'inventory_reservations'
        constraints = [
            models.UniqueConstraint(
                fields=['order_id', 'variant'],
                name='uq_reservation_order_variant',
            )
        ]

    def __str__(self) -> str:
        return f'Order {self.order_id} - {self.variant.sku} ({self.quantity}) [{self.status}]'

