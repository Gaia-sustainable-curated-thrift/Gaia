from django.contrib.auth import get_user_model
from django.core.checks import Tags, run_checks
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from accounts.models import WishlistItem
from products import cart
from products.models import BasketItem, Category, Product


class RoutingConfigurationTests(SimpleTestCase):
    def test_url_namespaces_are_unique(self):
        warnings = run_checks(tags=[Tags.urls])
        self.assertNotIn('urls.W005', [warning.id for warning in warnings])

    def test_product_chat_and_checkout_entry_points_still_resolve(self):
        for name, path in [
            ('products:home', '/products/'),
            ('chat:inbox', '/chat/'),
            ('transaction:checkout', '/transaction/checkout/'),
        ]:
            with self.subTest(name=name):
                self.assertEqual(reverse(name), path)
                self.assertEqual(resolve(path).view_name, name)


class ProductAdminSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser('catalog-admin', 'admin@example.test', 'test-password')
        cls.seller = get_user_model().objects.create_user('linen-seller')
        cls.shirt = Product.objects.create(seller=cls.seller, title='Linen Shirt', price=150000)
        cls.coat = Product.objects.create(seller=cls.admin, title='Wool Coat', price=300000)

    def test_admin_searches_existing_fields_and_handles_no_matches(self):
        self.client.force_login(self.admin)
        for query, expected in [('Linen', [self.shirt.pk]), ('linen-seller', [self.shirt.pk]), ('not-in-catalog', [])]:
            with self.subTest(query=query):
                response = self.client.get(reverse('admin:products_product_changelist'), {'q': query})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(list(response.context['cl'].queryset.values_list('pk', flat=True)), expected)


class ListingEmptyStateTests(TestCase):
    def test_home_categories_render_without_database_categories(self):
        response = self.client.get(reverse('products:home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['gender_tabs']), 2)
        for gender in ['women', 'men']:
            for category in ['tops', 'bottoms', 'shoes', 'bags']:
                self.assertContains(response, f'images/cat-{category}-{gender}.png')
                self.assertContains(response, f'/products/shop/{gender}/?category={gender}-{category}')

    def test_home_can_select_men_without_database_categories(self):
        response = self.client.get(reverse('products:home'), {'gender': 'men'})
        self.assertEqual(response.context['active_parent'].slug, 'men')
        self.assertTrue(response.context['gender_tabs'][1]['active'])

    def test_valid_departments_without_catalog_show_empty_state(self):
        for path in ['/products/shop/women/', '/products/shop/men/', '/products/picked/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'No products yet')
                self.assertFalse(response.context['has_active_products'])
                self.assertEqual(len(response.context['categories']), 4)

    def test_empty_active_tab_with_products_in_another_category(self):
        seller = get_user_model().objects.create_user('seller')
        parent = Category.objects.create(name='Women')
        tops = Category.objects.create(name='Tops', parent=parent)
        bags = Category.objects.create(name='Bags', parent=parent)
        Product.objects.create(seller=seller, title='Shirt', category=tops, price=100000)
        response = self.client.get(reverse('products:listing', args=['women']), {'category': bags.slug})
        self.assertFalse(response.context['has_active_products'])
        response = self.client.get(reverse('products:listing', args=['women']), {'category': tops.slug})
        self.assertTrue(response.context['has_active_products'])

    def test_unknown_paths_use_designed_404_in_both_debug_modes(self):
        for debug in [True, False]:
            with override_settings(DEBUG=debug):
                for path in ['/unknown/path/', '/products/missing-item/', '/products/shop/unknown/']:
                    with self.subTest(debug=debug, path=path):
                        response = self.client.get(path)
                        self.assertEqual(response.status_code, 404)
                        self.assertTemplateUsed(response, '404.html')
                        self.assertContains(response, 'Go back home', status_code=404)


class SharedNavbarTests(TestCase):
    def test_anonymous_navbar_uses_shared_component_without_member_actions(self):
        for path in ['/products/', '/products/search/', '/accounts/login/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertTemplateUsed(response, 'includes/navbar.html')
                self.assertContains(response, 'css/navbar.css')
                self.assertContains(response, 'nav-bag')
                self.assertContains(response, 'nav-login')
                self.assertNotContains(response, 'nav-wishlist')
                self.assertNotContains(response, 'nav-profile')

    def test_authenticated_navbar_is_shared_by_product_and_account_pages(self):
        user = get_user_model().objects.create_user('navbar-seller')
        self.client.force_login(user)
        for path in ['/products/', '/products/search/', '/products/sell/', '/accounts/profile/', '/accounts/wishlist/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertTemplateUsed(response, 'includes/navbar.html')
                self.assertContains(response, 'nav-wishlist')
                self.assertContains(response, 'nav-profile')
                self.assertNotContains(response, 'nav-login')
                self.assertNotContains(response, 'nav-orders')


class ProductModelTests(TestCase):
    def setUp(self):
        self.seller = get_user_model().objects.create_user('seller', password='pw')
        self.buyer = get_user_model().objects.create_user('buyer', password='pw')
        self.category = Category.objects.create(name='Outerwear')
        self.product = Product.objects.create(seller=self.seller, title='Trench Coat', price=300000, category=self.category)

    def test_slug_autogenerated(self):
        self.assertEqual(self.product.slug, 'trench-coat')

    def test_duplicate_titles_receive_distinct_slugs(self):
        second = Product.objects.create(seller=self.seller, title='Trench Coat', price=100000)
        third = Product.objects.create(seller=self.buyer, title='Trench Coat', price=200000)
        self.assertEqual(second.slug, 'trench-coat-2')
        self.assertEqual(third.slug, 'trench-coat-3')

    def test_long_duplicate_titles_keep_slugs_within_max_length(self):
        first = Product.objects.create(seller=self.seller, title='x' * 200, price=100000)
        second = Product.objects.create(seller=self.seller, title='x' * 200, price=100000)
        self.assertNotEqual(first.slug, second.slug)
        self.assertEqual(len(second.slug), 200)

    def test_non_latin_titles_receive_a_usable_slug(self):
        product = Product.objects.create(seller=self.seller, title='衣服', price=100000)
        self.assertEqual(product.slug, 'product')

    def test_changing_title_preserves_existing_detail_links(self):
        self.product.title = 'Renamed Coat'
        self.product.save()
        self.assertEqual(self.product.slug, 'trench-coat')

    def test_child_category_slug_includes_parent(self):
        parent = Category.objects.create(name='Women')
        child = Category.objects.create(name='Tops', parent=parent)
        self.assertEqual(parent.slug, 'women')
        self.assertEqual(child.slug, 'women-tops')

    def test_is_purchasable_only_when_available(self):
        self.assertTrue(self.product.is_purchasable)
        self.product.status = Product.Status.SOLD
        self.product.save()
        self.assertFalse(self.product.is_purchasable)

    def test_unique_basket_item_per_user(self):
        BasketItem.objects.create(user=self.buyer, product=self.product)
        with self.assertRaises(IntegrityError):
            BasketItem.objects.create(user=self.buyer, product=self.product)


class BagTests(TestCase):
    def setUp(self):
        self.seller = get_user_model().objects.create_user('seller', password='pw')
        self.category = Category.objects.create(name='Outerwear')
        self.product = Product.objects.create(seller=self.seller, title='Trench Coat', price=300000, category=self.category)

    def test_add_to_bag_stores_in_session(self):
        response = self.client.post(reverse('products:bag_add', args=[self.product.slug]))
        self.assertRedirects(response, reverse('products:detail', args=[self.product.slug]))
        self.assertEqual(cart.count(self.client.session), 1)

    def test_ajax_count_tracks_add_remove_and_undo_without_stale_toast(self):
        headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        add = reverse('products:bag_add', args=[self.product.slug])
        for expected in [1, 2]:
            response = self.client.post(add, **headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['bag_count'], expected)
        response = self.client.post(
            reverse('products:bag_set', args=[self.product.slug]), {'quantity': 0}, **headers,
        )
        self.assertEqual(response.json()['bag_count'], 0)
        response = self.client.post(reverse('products:bag_undo'), **headers)
        self.assertEqual(response.json()['bag_count'], 2)
        response = self.client.get(reverse('products:home'))
        self.assertContains(response, 'aria-label="Shopping bag, 2 items"')
        self.assertContains(response, 'data-bag-count')
        self.assertNotContains(response, 'toast toast--added')

    def test_detail_shows_added_toast(self):
        self.client.post(reverse('products:bag_add', args=[self.product.slug]))
        response = self.client.get(reverse('products:detail', args=[self.product.slug]))
        self.assertContains(response, 'to bag')

    def test_decrease_to_zero_removes_and_offers_undo(self):
        self.client.post(reverse('products:bag_add', args=[self.product.slug]))
        self.client.post(reverse('products:bag_set', args=[self.product.slug]), {'quantity': 0})
        self.assertEqual(cart.count(self.client.session), 0)
        response = self.client.get(reverse('products:detail', args=[self.product.slug]))
        self.assertContains(response, 'Item removed')
        self.assertContains(response, 'Undo')

    def test_undo_restores_removed_item(self):
        self.client.post(reverse('products:bag_add', args=[self.product.slug]))
        self.client.post(reverse('products:bag_set', args=[self.product.slug]), {'quantity': 0})
        self.client.post(reverse('products:bag_undo'))
        self.assertEqual(cart.count(self.client.session), 1)

    def test_wish_add_redirects_anonymous_to_login(self):
        response = self.client.post(reverse('products:wish_add', args=[self.product.slug]))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_wish_add_saves_for_authenticated_user(self):
        self.client.force_login(self.seller)
        self.client.post(reverse('products:wish_add', args=[self.product.slug]))
        self.assertTrue(WishlistItem.objects.filter(user=self.seller, product_key=self.product.slug).exists())

    def test_checkout_links_to_login_for_anonymous(self):
        self.client.post(reverse('products:bag_add', args=[self.product.slug]))
        response = self.client.get(reverse('products:detail', args=[self.product.slug]))
        self.assertContains(response, '/accounts/login/?next=')


class SellTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('seller', password='pw')
        self.parent = Category.objects.create(name='Women')
        self.child = Category.objects.create(name='Tops', parent=self.parent)
        self.url = reverse('products:sell')

    def test_sell_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_sell_form_renders_for_seller(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Select maximum 5 photos')
        self.assertContains(response, 'List item')

    def test_listing_creates_product(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            'title': 'Linen Shirt',
            'category': self.child.pk,
            'parent': self.parent.slug,
            'price': '1.250.000',
            'condition': Product.Condition.EXCELLENT,
        })
        product = Product.objects.get(title='Linen Shirt')
        self.assertRedirects(response, reverse('products:detail', args=[product.slug]))
        self.assertEqual(product.price, 1250000)
        self.assertEqual(product.seller, self.user)
        self.assertEqual(product.category, self.child)
        self.assertEqual(product.condition, Product.Condition.EXCELLENT)

    def test_listing_requires_title_and_price(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'title': '', 'category': '', 'price': ''})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Product.objects.count(), 0)
        self.assertContains(response, 'sell-errors')

    def test_invalid_prices_show_errors_without_creating_products(self):
        self.client.force_login(self.user)
        for price in ['-10.000', 'abc100', '0', '2147483648']:
            with self.subTest(price=price):
                response = self.client.post(self.url, {'title': 'Shirt', 'category': self.child.pk, 'price': price})
                self.assertEqual(response.status_code, 200)
                self.assertIn('price', response.context['form'].errors)
                self.assertEqual(Product.objects.count(), 0)

    def test_invalid_category_returns_a_form_error_not_a_server_error(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {'title': 'Shirt', 'category': 'not-a-number', 'price': '100000'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('category', response.context['form'].errors)
        self.assertEqual(Product.objects.count(), 0)

    def test_non_image_upload_does_not_create_a_partial_listing(self):
        self.client.force_login(self.user)
        photo = SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')
        response = self.client.post(self.url, {'title': 'Shirt', 'category': self.child.pk, 'price': '100000', 'photos': photo})
        self.assertEqual(response.status_code, 200)
        self.assertIn('photos', response.context['form'].errors)
        self.assertEqual(Product.objects.count(), 0)

    def test_duplicate_listing_titles_do_not_crash(self):
        self.client.force_login(self.user)
        data = {'title': 'Linen Shirt', 'category': self.child.pk, 'price': '100000'}
        for _ in range(2):
            self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(set(Product.objects.values_list('slug', flat=True)), {'linen-shirt', 'linen-shirt-2'})

    def test_seller_is_taken_from_session_not_posted_user_id(self):
        other = get_user_model().objects.create_user('other-seller')
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            'title': 'Shirt', 'category': self.child.pk, 'price': '100000', 'seller': other.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Product.objects.get(title='Shirt').seller, self.user)

    def test_failed_submission_preserves_title_category_and_condition(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url, {
            'title': 'Keep This Title', 'category': self.child.pk, 'condition': 'excellent', 'price': '-100',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="Keep This Title"')
        self.assertEqual(response.context['selected_category'], self.child)
        self.assertEqual(response.context['form']['condition'].value(), 'excellent')
