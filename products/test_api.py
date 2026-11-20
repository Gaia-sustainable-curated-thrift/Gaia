from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Category, Product


class ProductApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = get_user_model().objects.create_user(
            username='seller',
            password='test-password',
        )
        self.other = get_user_model().objects.create_user(
            username='other',
            password='test-password',
        )
        self.category = Category.objects.create(name='Tops')
        self.product = Product.objects.create(
            seller=self.seller,
            title='Vintage jacket',
            price=150000,
            category=self.category,
        )

    def test_list_returns_product_json(self):
        response = self.client.get('/api/products/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['title'], 'Vintage jacket')
        self.assertEqual(response.data[0]['category_name'], 'Tops')

    def test_detail_returns_product(self):
        response = self.client.get(f'/api/products/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['price'], 150000)

    def test_authenticated_user_can_create_listing(self):
        self.client.force_authenticate(self.seller)
        response = self.client.post('/api/products/', {
            'title': 'Second hand shirt',
            'price': 50000,
            'category': self.category.pk,
            'condition': Product.Condition.GOOD,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Product.objects.get(pk=response.data['id']).seller, self.seller)

    def test_only_owner_can_edit_or_delete_listing(self):
        self.client.force_authenticate(self.other)
        response = self.client.patch(
            f'/api/products/{self.product.pk}/',
            {'title': 'Changed'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.delete(f'/api/products/{self.product.pk}/').status_code, 403)

    def test_owner_can_update_and_soft_delete_listing(self):
        self.client.force_authenticate(self.seller)
        response = self.client.patch(
            f'/api/products/{self.product.pk}/',
            {'title': 'Updated jacket'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Updated jacket')
        self.assertEqual(self.client.delete(f'/api/products/{self.product.pk}/').status_code, 204)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
