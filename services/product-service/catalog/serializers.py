from decimal import Decimal
from rest_framework import serializers
from catalog.models import Brand, Category, Product, ProductVariant




class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'is_active']
        read_only_fields = ['id']



class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ['id', 'name', 'slug']
        read_only_fields = ['id']



class ProductVariantOutputSerializer(serializers.ModelSerializer):
    effective_price = serializers.DecimalField(max_digits=12, decimal_places=2, required=True)
    available_quantity = serializers.IntegerField(source='inventory.available_quantity', required=True)

    class Meta:
        model = ProductVariant
        fields = ['id', 'sku', 'attributes', 'price_override', 'effective_price', 'available_quantity', 'is_active']



class ProductOutputSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    variants = ProductVariantOutputSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'description', 'base_price', 'category', 'brand', 'variants', 'is_active', 'created_at']



class VariantCreateInputSerializer(serializers.Serializer):
    sku = serializers.CharField(max_length=100)
    attributes = serializers.DictField(required=False, default=dict)
    price_override = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True, default=None)
    initial_stock = serializers.IntegerField(min_value=0, default=0)



class ProductCreateInputSerializer(serializers.Serializer):
    category_id = serializers.UUIDField()
    brand_id = serializers.UUIDField()
    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=260)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    base_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.00'))
    variants_data = VariantCreateInputSerializer(many=True, min_length=1)



class ReserveItemInputSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)



class ReserveStockInputSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    items = ReserveItemInputSerializer(many=True, min_length=1)
