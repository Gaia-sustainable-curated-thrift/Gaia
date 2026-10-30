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
            price=100000, condition='excellent', description='Soft summer fabric, wardrobe sample', style_tags='minimalist',
        )
        cls.jacket = Product.objects.create(seller=cls.seller, title='Denim Jacket', category=men_tops, price=180000, condition='good', description='Wardrobe sample')
        cls.bag = Product.objects.create(seller=cls.seller, title='Shoulder Bag', category=women_bags, price=250000, condition='excellent', description='Wardrobe sample')
        cls.shoes = Product.objects.create(seller=cls.seller, title='Running Sneakers', category=men_shoes, price=80000, condition='signs_of_wear', status='sold', description='Wardrobe sample')

    def results(self, **parameters):
        parameters.setdefault('q', 'wardrobe')
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
        for value in ['invalid', '²']:
            with self.subTest(value=value):
                _, ids = self.results(price_from=value, price_to=value)
                self.assertEqual(ids, {self.shirt.pk, self.jacket.pk, self.bag.pk})

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

    def test_empty_search_redirects_instead_of_showing_an_empty_search_heading(self):
        for parameters in [{}, {'q': ''}, {'q': '   '}]:
            with self.subTest(parameters=parameters):
                response = self.client.get(reverse('products:search'), parameters)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse('products:home'))
                self.assertContains(self.client.get(response.url), 'Enter a search term.')

    def test_search_trims_surrounding_whitespace(self):
        response, ids = self.results(q='  Linen  ')
        self.assertEqual(response.context['q'], 'Linen')
        self.assertEqual(ids, {self.shirt.pk})

    def test_sold_items_are_hidden_from_all_public_catalogs(self):
        for path in [reverse('products:home'), reverse('products:picked'), reverse('products:listing', args=['men']), reverse('products:listing', args=['women'])]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                products = response.context.get('products', response.context.get('picked'))
                self.assertNotIn(self.shoes.pk, [product.pk for product in products])
                self.assertNotContains(response, self.shoes.title)
        _, ids = self.results(q='Running Sneakers')
        self.assertEqual(ids, set())

    def test_sold_detail_is_hidden_but_owner_management_still_works(self):
        detail = reverse('products:detail', args=[self.shoes.slug])
        self.assertEqual(self.client.get(detail).status_code, 404)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(detail).status_code, 200)
        self.assertTrue(self.seller.products.filter(pk=self.shoes.pk, status=Product.Status.SOLD).exists())
        self.assertEqual(self.client.get(reverse('products:edit', args=[self.shoes.slug])).status_code, 200)

    def test_related_products_never_include_sold_items(self):
        self.shoes.category = self.women_tops
        self.shoes.save(update_fields=['category'])
        response = self.client.get(reverse('products:detail', args=[self.shirt.slug]))
        self.assertNotIn(self.shoes.pk, [product.pk for product in response.context['related']])

    def test_sold_products_cannot_be_saved_to_wishlist(self):
        from accounts.models import WishlistItem

        self.client.force_login(self.seller)
        response = self.client.post(reverse('products:wish_add', args=[self.shoes.slug]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 404)
        self.assertFalse(WishlistItem.objects.filter(product_key=self.shoes.slug).exists())

    def test_sold_wishlist_items_are_hidden_without_deleting_snapshots(self):
        from accounts.models import WishlistItem

        saved = WishlistItem.objects.create(user=self.seller, product_key=self.shoes.slug, title=self.shoes.title, price=self.shoes.price)
        visible = WishlistItem.objects.create(user=self.seller, product_key=self.shirt.slug, title=self.shirt.title, price=self.shirt.price)
        self.client.force_login(self.seller)
        response = self.client.get(reverse('wishlist'))
        self.assertEqual(list(response.context['items']), [visible])
        self.assertTrue(WishlistItem.objects.filter(pk=saved.pk).exists())
        self.assertEqual(self.client.get(reverse('profile')).context['wishlist_count'], 1)

    def test_seller_name_and_photo_link_to_the_existing_public_seller_page(self):
        url = reverse('reviews:seller_reviews', args=[self.seller.pk])
        response = self.client.get(reverse('products:detail', args=[self.shirt.slug]))
        self.assertContains(response, f'class="pdp-avatar" href="{url}"')
        self.assertContains(response, f'class="pdp-username" href="{url}"')
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_sidebar_category_links_select_the_requested_product_tab(self):
        page = self.client.get(reverse('products:home'))
        for name in ['tops', 'bottoms', 'shoes', 'bags']:
            with self.subTest(category=name):
                url = reverse('products:picked') + '?category=' + name
                self.assertContains(page, f'href="{url}"')
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['active_category'].name.lower(), name)
        self.assertContains(page, 'type="search" name="q"')
