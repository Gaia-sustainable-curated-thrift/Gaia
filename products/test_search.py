from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product, ProductImage


class ProductSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = get_user_model().objects.create_user('search-seller')
        women = Category.objects.create(name='Women')
        men = Category.objects.create(name='Men')
        cls.women_tops = Category.objects.create(name='Tops', parent=women)
        men_tops = Category.objects.create(name='Tops', parent=men)
        women_bags = Category.objects.create(name='Bags', parent=women)
        men_shoes = Category.objects.create(name='Shoes', parent=men)
        cls.shirt = Product.objects.create(
            seller=cls.seller, title='Linen Shirt', category=cls.women_tops,
            price=100000, condition='excellent', description='Soft summer fabric', style_tags='minimalist',
        )
        cls.jacket = Product.objects.create(seller=cls.seller, title='Denim Jacket', category=men_tops, price=180000, condition='good')
        cls.bag = Product.objects.create(seller=cls.seller, title='Shoulder Bag', category=women_bags, price=250000, condition='excellent')
        cls.shoes = Product.objects.create(seller=cls.seller, title='Running Sneakers', category=men_shoes, price=80000, condition='signs_of_wear', status='sold')

    def results(self, **parameters):
        response = self.client.get(reverse('products:search'), parameters)
        self.assertEqual(response.status_code, 200)
        return response, set(response.context['products'].values_list('pk', flat=True))

    def test_keyword_searches_title_description_tags_and_categories(self):
        for query, expected in [
            ('linen', {self.shirt.pk}),
            ('SUMMER', {self.shirt.pk}),
            ('minimalist', {self.shirt.pk}),
            ('Bags', {self.bag.pk}),
            ('Women', {self.shirt.pk, self.bag.pk}),
        ]:
            with self.subTest(query=query):
                _, ids = self.results(q=query)
                self.assertEqual(ids, expected)

    def test_price_range_includes_its_boundaries(self):
        response, ids = self.results(price_from='100000', price_to='180000')
        self.assertEqual(ids, {self.shirt.pk, self.jacket.pk})
        self.assertEqual(response.context['result_count'], 2)

    def test_filters_can_be_combined(self):
        _, ids = self.results(gender=['women'], category=['Tops'], condition=['excellent'], price_from='90000', price_to='150000')
        self.assertEqual(ids, {self.shirt.pk})

    def test_multiple_category_and_condition_values_are_supported(self):
        _, ids = self.results(category=['Tops', 'Bags'], condition=['good', 'excellent'])
        self.assertEqual(ids, {self.shirt.pk, self.jacket.pk, self.bag.pk})

    def test_unmatched_search_and_conflicting_filters_return_empty_results(self):
        for parameters in [{'q': 'no-such-item'}, {'price_from': '300000', 'price_to': '100000'}, {'gender': ['women'], 'category': ['Shoes']}]:
            with self.subTest(parameters=parameters):
                response, ids = self.results(**parameters)
                self.assertEqual(ids, set())
                self.assertEqual(response.context['result_count'], 0)

    def test_invalid_price_bounds_do_not_crash_or_apply_an_unintended_filter(self):
        _, ids = self.results(price_from='invalid', price_to='also-invalid')
        self.assertEqual(ids, {self.shirt.pk, self.jacket.pk, self.bag.pk, self.shoes.pk})

    def test_category_facets_deduplicate_shared_department_names(self):
        response, _ = self.results(category=['Tops'])
        tops = [facet for facet in response.context['category_facets'] if facet['name'] == 'Tops']
        self.assertEqual(len(tops), 1)
        self.assertEqual(tops[0]['count'], 2)
        self.assertTrue(tops[0]['checked'])

    def test_related_products_prefer_the_same_category(self):
        related = Product.objects.create(seller=self.seller, title='Cotton Shirt', category=self.women_tops, price=120000)
        response = self.client.get(reverse('products:detail', args=[self.shirt.slug]))
        self.assertEqual(list(response.context['related']), [related])

    def test_primary_image_is_first_in_the_detail_gallery(self):
        ProductImage.objects.create(product=self.shirt, image='products/front.png', order=0)
        cover = ProductImage.objects.create(product=self.shirt, image='products/back.png', order=1, is_primary=True)
        response = self.client.get(reverse('products:detail', args=[self.shirt.slug]))
        self.assertEqual(response.context['images'][0], cover)
