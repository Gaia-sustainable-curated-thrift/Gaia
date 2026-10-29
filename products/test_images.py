from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Product, ProductImage


class PrimaryImageQueryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seller = get_user_model().objects.create_user('gallery-seller')
        cls.product = Product.objects.create(seller=seller, title='Gallery Shirt', price=150000)
        cls.front = ProductImage.objects.create(product=cls.product, image='products/front.png', order=0)
        cls.cover = ProductImage.objects.create(product=cls.product, image='products/cover.png', order=1, is_primary=True)

    def test_prefetched_primary_image_requires_no_additional_queries(self):
        product = Product.objects.prefetch_related('images').get(pk=self.product.pk)
        with self.assertNumQueries(0):
            self.assertEqual(product.primary_image, self.cover)

    def test_without_prefetch_primary_image_is_loaded_in_one_query(self):
        product = Product.objects.get(pk=self.product.pk)
        with self.assertNumQueries(1):
            self.assertEqual(product.primary_image, self.cover)

    def test_gallery_order_is_used_when_no_cover_is_marked(self):
        self.cover.is_primary = False
        self.cover.save(update_fields=['is_primary'])
        product = Product.objects.prefetch_related('images').get(pk=self.product.pk)
        with self.assertNumQueries(0):
            self.assertEqual(product.primary_image, self.front)
