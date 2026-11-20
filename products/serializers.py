from rest_framework import serializers

from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    seller_name = serializers.CharField(source='seller.username', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            'id', 'title', 'slug', 'description', 'price', 'category',
            'category_name', 'condition', 'style_tags', 'status',
            'seller_name', 'image_url', 'created_at',
        )
        read_only_fields = (
            'id', 'slug', 'status', 'seller_name', 'image_url', 'created_at',
        )

    def get_image_url(self, product):
        image = product.primary_image
        if not image:
            return None
        request = self.context.get('request')
        url = image.image.url
        return request.build_absolute_uri(url) if request else url
