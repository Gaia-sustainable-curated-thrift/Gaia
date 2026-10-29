from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.checks import Tags, run_checks
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from accounts.models import AccountOrder, WishlistItem
from products import cart
from products.models import BasketItem, Category, Product
from products.test_forms import uploaded_photo


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


class WishlistSaveTests(TestCase):
    ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    @classmethod
    def setUpTestData(cls):
        cls.seller = get_user_model().objects.create_user('wishlist-seller')
        cls.viewer = get_user_model().objects.create_user('wishlist-viewer')
        cls.other = get_user_model().objects.create_user('wishlist-other')
        cls.product = Product.objects.create(seller=cls.seller, title='Wishlist Shirt', price=150000, condition='excellent')

    def setUp(self):
        self.client.force_login(self.viewer)
        self.url = reverse('products:wish_add', args=[self.product.slug])
        self.detail_url = reverse('products:detail', args=[self.product.slug])

    def test_ajax_save_returns_a_heart_toast_and_saves_the_current_snapshot(self):
        photo = self.product.images.create(image='products/wishlist-cover.png', is_primary=True)
        response = self.client.post(self.url, {'user': self.other.pk}, **self.ajax)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(response.json()['toast']['icon'], 'heart')
        self.assertIn('Saved', response.json()['toast']['text'])
        self.assertEqual(response.json()['saved_count'], 1)
        item = WishlistItem.objects.get(user=self.viewer, product_key=self.product.slug)
        self.assertEqual(item.title, self.product.title)
        self.assertEqual(item.price, self.product.price)
        self.assertEqual(item.condition, 'Excellent')
        self.assertEqual(item.image, photo.image.url)
        self.assertFalse(item.removed)
        self.assertFalse(WishlistItem.objects.filter(user=self.other).exists())
        self.assertNotIn('bag_toast', self.client.session)
        self.assertNotContains(self.client.get(self.detail_url), 'toast toast--added')

    def test_repeated_save_does_not_duplicate_the_item_or_counter(self):
        for _ in range(2):
            response = self.client.post(self.url, **self.ajax)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['saved_count'], 1)
        self.assertEqual(WishlistItem.objects.filter(user=self.viewer, product_key=self.product.slug).count(), 1)

    def test_saving_a_removed_item_restores_it_and_refreshes_its_data(self):
        item = WishlistItem.objects.create(
            user=self.viewer, product_key=self.product.slug, title='Old title', price=1, removed=True,
        )
        response = self.client.post(self.url, **self.ajax)
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertFalse(item.removed)
        self.assertEqual(item.title, self.product.title)
        self.assertEqual(item.price, self.product.price)
        self.assertEqual(WishlistItem.objects.count(), 1)

    def test_saved_counter_counts_only_active_saves_for_this_product(self):
        WishlistItem.objects.create(user=self.other, product_key=self.product.slug, title='Shirt', price=150000)
        WishlistItem.objects.create(user=self.seller, product_key=self.product.slug, title='Shirt', price=150000, removed=True)
        WishlistItem.objects.create(user=self.viewer, product_key='another-product', title='Other', price=100000)
        response = self.client.post(self.url, **self.ajax)
        self.assertEqual(response.json()['saved_count'], 2)
        page = self.client.get(self.detail_url)
        self.assertEqual(page.context['saved_count'], 2)
        self.assertTrue(page.context['wishlist_saved'])

    def test_detail_saved_state_follows_account_remove_and_undo(self):
        page = self.client.get(self.detail_url)
        self.assertFalse(page.context['wishlist_saved'])
        self.assertEqual(page.context['saved_count'], 0)
        self.client.post(self.url, **self.ajax)
        item = WishlistItem.objects.get(user=self.viewer, product_key=self.product.slug)
        page = self.client.get(self.detail_url)
        self.assertTrue(page.context['wishlist_saved'])
        self.assertContains(page, 'Saved to wishlist')
        self.client.post(reverse('wishlist_remove', args=[item.pk]))
        page = self.client.get(self.detail_url)
        self.assertFalse(page.context['wishlist_saved'])
        self.assertEqual(page.context['saved_count'], 0)
        self.client.post(reverse('wishlist_undo'))
        self.assertTrue(self.client.get(self.detail_url).context['wishlist_saved'])

    def test_anonymous_ajax_gets_a_login_url_back_to_the_product_page(self):
        self.client.logout()
        response = self.client.post(self.url, **self.ajax)
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()['ok'])
        login = urlparse(response.json()['login_url'])
        self.assertEqual(login.path, reverse('login'))
        self.assertEqual(parse_qs(login.query)['next'], [self.detail_url])
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_anonymous_native_post_also_returns_to_a_gettable_page_after_login(self):
        self.client.logout()
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(parse_qs(urlparse(response.url).query)['next'], [self.detail_url])

    def test_native_save_redirects_with_a_one_shot_success_toast(self):
        response = self.client.post(self.url, {'next': self.detail_url})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.detail_url)
        page = self.client.get(response.url)
        self.assertEqual(page.context['bag_toast']['icon'], 'heart')
        self.assertContains(page, 'toast toast--added')
        self.assertNotContains(self.client.get(response.url), 'toast toast--added')

    def test_mutations_require_post_and_csrf(self):
        for method in [self.client.get, self.client.put, self.client.delete]:
            self.assertEqual(method(self.url).status_code, 405)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.viewer)
        self.assertEqual(client.post(self.url, **self.ajax).status_code, 403)
        self.assertEqual(WishlistItem.objects.count(), 0)

    def test_missing_product_is_not_added(self):
        response = self.client.post(reverse('products:wish_add', args=['missing-product']), **self.ajax)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(WishlistItem.objects.count(), 0)


class EditListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('listing-owner')
        cls.other = get_user_model().objects.create_user('other-user')
        women = Category.objects.create(name='Women')
        men = Category.objects.create(name='Men')
        cls.category = Category.objects.create(name='Tops', parent=women)
        cls.other_category = Category.objects.create(name='Tops', parent=men)
        cls.product = Product.objects.create(
            seller=cls.owner, title='Original Shirt', category=cls.category,
            condition='excellent', price=125000, description='Existing description',
        )
        cls.front = cls.product.images.create(image='products/front.png', order=0)
        cls.cover = cls.product.images.create(image='products/cover.png', order=4, is_primary=True)

    def data(self, **changes):
        data = {
            'title': 'Updated Shirt', 'category': self.other_category.pk,
            'condition': 'good', 'price': '175.000',
        }
        data.update(changes)
        return data

    def edit_url(self):
        return reverse('products:edit', args=[self.product.slug])

    def test_edit_requires_login_for_get_and_post(self):
        for method in [self.client.get, self.client.post]:
            response = method(self.edit_url(), self.data())
            self.assertEqual(response.status_code, 302)
            self.assertIn('/accounts/login/', response.url)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Original Shirt')

    def test_only_the_owner_sees_the_edit_link(self):
        detail_url = reverse('products:detail', args=[self.product.slug])
        self.assertNotContains(self.client.get(detail_url), self.edit_url())
        self.client.force_login(self.other)
        response = self.client.get(detail_url)
        self.assertNotContains(response, self.edit_url())
        self.assertContains(response, reverse('chat:start', args=[self.product.pk]))
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(detail_url), self.edit_url())

    def test_another_user_cannot_read_or_submit_the_edit_form(self):
        self.client.force_login(self.other)
        for method in [self.client.get, self.client.post]:
            self.assertEqual(method(self.edit_url(), self.data()).status_code, 404)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Original Shirt')
        self.assertEqual(self.product.price, 125000)

    def test_staff_status_does_not_bypass_listing_ownership(self):
        self.other.is_staff = True
        self.other.is_superuser = True
        self.other.save(update_fields=['is_staff', 'is_superuser'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.edit_url(), self.data()).status_code, 404)
        self.product.refresh_from_db()
        self.assertEqual(self.product.seller, self.owner)

    def test_owner_get_reuses_the_prefilled_form_without_changing_data(self):
        self.client.force_login(self.owner)
        original_updated_at = self.product.updated_at
        response = self.client.get(self.edit_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'products/sell.html')
        self.assertContains(response, 'Save changes')
        self.assertContains(response, 'value="Original Shirt"')
        self.assertEqual(response.context['form']['condition'].value(), 'excellent')
        self.assertEqual(response.context['selected_category'], self.category)
        self.assertEqual(response.context['cover_id'], self.cover.pk)
        self.assertEqual(len(response.context['existing_images']), 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.updated_at, original_updated_at)

    def test_owner_updates_fields_without_creating_a_new_product_or_replacing_photos(self):
        self.client.force_login(self.owner)
        old_slug = self.product.slug
        photo_ids = set(self.product.images.values_list('pk', flat=True))
        response = self.client.post(self.edit_url(), self.data())
        self.assertRedirects(response, reverse('products:detail', args=[old_slug]), fetch_redirect_response=False)
        self.product.refresh_from_db()
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(self.product.title, 'Updated Shirt')
        self.assertEqual(self.product.category, self.other_category)
        self.assertEqual(self.product.price, 175000)
        self.assertEqual(self.product.condition, 'good')
        self.assertEqual(self.product.seller, self.owner)
        self.assertEqual(self.product.slug, old_slug)
        self.assertEqual(self.product.description, 'Existing description')
        self.assertEqual(set(self.product.images.values_list('pk', flat=True)), photo_ids)
        self.assertEqual(self.product.primary_image.pk, self.cover.pk)
        self.assertContains(self.client.get(response.url), 'Listing updated.')
        self.assertNotContains(self.client.get(response.url), 'Listing updated.')

    def test_invalid_submission_does_not_update_the_product(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.edit_url(), self.data(price='-100'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('price', response.context['form'].errors)
        self.assertContains(response, 'value="Updated Shirt"')
        self.assertEqual(len(response.context['existing_images']), 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Original Shirt')
        self.assertEqual(self.product.price, 125000)

    def test_manipulated_seller_slug_and_status_are_ignored(self):
        self.product.status = Product.Status.SOLD
        self.product.save(update_fields=['status'])
        old_slug = self.product.slug
        self.client.force_login(self.owner)
        response = self.client.post(self.edit_url(), self.data(seller=self.other.pk, slug='changed-url', status='available'))
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.seller, self.owner)
        self.assertEqual(self.product.slug, old_slug)
        self.assertEqual(self.product.status, Product.Status.SOLD)

    def test_new_photos_are_appended_up_to_five_without_changing_the_cover(self):
        self.client.force_login(self.owner)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post(self.edit_url(), self.data(
                photos=[uploaded_photo(f'extra-{index}.png') for index in range(3)],
            ))
            self.assertEqual(response.status_code, 302)
            photos = list(self.product.images.all())
            self.assertEqual([photo.order for photo in photos], [0, 4, 5, 6, 7])
            self.assertEqual(sum(photo.is_primary for photo in photos), 1)
            self.assertEqual(self.product.primary_image.pk, self.cover.pk)
            self.assertTrue(all(photo.image.storage.exists(photo.image.name) for photo in photos[2:]))

    def test_existing_and_new_photos_cannot_exceed_five(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.edit_url(), self.data(
            photos=[uploaded_photo(f'extra-{index}.png') for index in range(4)],
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn('photos', response.context['form'].errors)
        self.assertEqual(self.product.images.count(), 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Original Shirt')

    def test_first_photo_added_to_an_imageless_listing_becomes_the_cover(self):
        self.product.images.all().delete()
        self.client.force_login(self.owner)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post(self.edit_url(), self.data(photos=[uploaded_photo()]))
            self.assertEqual(response.status_code, 302)
            photo = self.product.images.get()
            self.assertTrue(photo.is_primary)
            self.assertEqual(photo.order, 0)

    def test_non_image_upload_leaves_existing_photos_unchanged(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.edit_url(), self.data(
            photos=SimpleUploadedFile('fake.png', b'not an image', content_type='image/png'),
        ))
        self.assertEqual(response.status_code, 200)
        self.assertIn('photos', response.context['form'].errors)
        self.assertEqual(self.product.images.count(), 2)

    def test_csrf_is_required_for_edit(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.edit_url(), self.data()).status_code, 403)
        self.product.refresh_from_db()
        self.assertEqual(self.product.title, 'Original Shirt')

    def test_unknown_listing_returns_404(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(reverse('products:edit', args=['missing-listing'])).status_code, 404)

    def test_edit_keeps_existing_chat_product_references(self):
        from chat.models import Conversation

        conversation = Conversation.objects.create(product=self.product, buyer=self.other, seller=self.owner)
        old_slug = self.product.slug
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.edit_url(), self.data()).status_code, 302)
        conversation.refresh_from_db()
        self.assertEqual(conversation.product_id, self.product.pk)
        self.assertEqual(conversation.product.slug, old_slug)
        self.assertEqual(conversation.product.title, 'Updated Shirt')


class DeleteListingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('delete-owner')
        cls.other = get_user_model().objects.create_user('delete-other')
        cls.product = Product.objects.create(seller=cls.owner, title='Delete This Shirt', price=125000)

    def delete_url(self):
        return reverse('products:delete', args=[self.product.slug])

    def test_anonymous_delete_requires_login(self):
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_another_user_cannot_delete_the_listing(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.delete_url(), {'seller': self.owner.pk}).status_code, 404)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_staff_status_does_not_bypass_ownership(self):
        self.other.is_staff = True
        self.other.is_superuser = True
        self.other.save(update_fields=['is_staff', 'is_superuser'])
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.delete_url()).status_code, 404)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_only_post_can_delete(self):
        self.client.force_login(self.owner)
        for method in [self.client.get, self.client.head, self.client.put, self.client.delete]:
            with self.subTest(method=method.__name__):
                self.assertEqual(method(self.delete_url()).status_code, 405)
                self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.delete_url()).status_code, 403)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())

    def test_only_owner_sees_the_confirmation_dialog_and_delete_action(self):
        detail = reverse('products:detail', args=[self.product.slug])
        self.assertNotContains(self.client.get(detail), 'delete-listing-dialog')
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get(detail), 'delete-listing-dialog')
        self.client.force_login(self.owner)
        response = self.client.get(detail)
        self.assertContains(response, 'id="delete-listing-dialog"')
        self.assertContains(response, self.delete_url())
        self.assertContains(response, 'form method="dialog"')
        self.assertContains(response, 'permanently removed')

    def test_delete_removes_only_the_chosen_product_and_its_image_records(self):
        photo = self.product.images.create(image='products/deleted-photo.png')
        keep = Product.objects.create(seller=self.owner, title='Keep This Shirt', price=150000)
        old_detail = reverse('products:detail', args=[self.product.slug])
        self.client.force_login(self.owner)
        response = self.client.post(self.delete_url())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('products:home'))
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertFalse(type(photo).objects.filter(pk=photo.pk).exists())
        self.assertTrue(Product.objects.filter(pk=keep.pk).exists())
        self.assertContains(self.client.get(response.url), 'Listing deleted.')
        self.assertNotContains(self.client.get(response.url), 'Listing deleted.')
        self.assertEqual(self.client.get(old_detail).status_code, 404)

    def test_sold_listing_can_be_deleted_by_its_owner(self):
        self.product.status = Product.Status.SOLD
        self.product.save(update_fields=['status'])
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.delete_url()).status_code, 302)
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_deleted_and_unknown_slugs_return_404(self):
        self.client.force_login(self.owner)
        url = self.delete_url()
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.post(url).status_code, 404)
        self.assertEqual(self.client.post(reverse('products:delete', args=['missing-listing'])).status_code, 404)

    def test_deleted_item_is_removed_from_the_current_bag_and_undo_entry(self):
        keep = Product.objects.create(seller=self.owner, title='Keep In Bag', price=150000)
        self.client.force_login(self.owner)
        session = self.client.session
        session['bag'] = {str(self.product.pk): 2, str(keep.pk): 1}
        session['bag_undo'] = {'product_id': self.product.pk, 'quantity': 2}
        session.save()
        self.assertEqual(self.client.post(self.delete_url()).status_code, 302)
        self.assertEqual(self.client.session['bag'], {str(keep.pk): 1})
        self.assertNotIn('bag_undo', self.client.session)

    def test_undo_for_a_different_product_is_preserved(self):
        keep = Product.objects.create(seller=self.owner, title='Other Removed Item', price=150000)
        self.client.force_login(self.owner)
        session = self.client.session
        session['bag_undo'] = {'product_id': keep.pk, 'quantity': 1}
        session.save()
        self.assertEqual(self.client.post(self.delete_url()).status_code, 302)
        self.assertEqual(self.client.session['bag_undo']['product_id'], keep.pk)

    def test_existing_chat_and_messages_survive_product_deletion(self):
        from chat.models import Conversation, Message

        conversation = Conversation.objects.create(product=self.product, buyer=self.other, seller=self.owner)
        text = Message.objects.create(conversation=conversation, sender=self.other, body='Is this still available?')
        shared = Message.objects.create(conversation=conversation, sender=self.other, kind=Message.Kind.PRODUCT, product=self.product)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.delete_url()).status_code, 302)
        conversation.refresh_from_db()
        text.refresh_from_db()
        shared.refresh_from_db()
        self.assertIsNone(conversation.product_id)
        self.assertIsNone(shared.product_id)
        self.assertEqual(text.body, 'Is this still available?')
        self.assertEqual(conversation.messages.count(), 2)
        self.assertContains(self.client.get(reverse('chat:room', args=[conversation.pk])), 'Is this still available?')

    def test_order_and_wishlist_snapshots_keep_their_data_and_picture(self):
        self.client.force_login(self.owner)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            photo = self.product.images.create(image=uploaded_photo('order-picture.png'), is_primary=True)
            image_url = photo.image.url
            order = AccountOrder.objects.create(
                user=self.other, number='DELETE-TEST-001', date=timezone.localdate(), status='completed',
                title=self.product.title, condition='Good', image=image_url,
                subtotal=self.product.price, recipient='Buyer', address='Jakarta',
            )
            saved = WishlistItem.objects.create(
                user=self.other, product_key=self.product.slug, title=self.product.title,
                condition='Good', price=self.product.price, image=image_url,
            )
            self.assertEqual(self.client.post(self.delete_url()).status_code, 302)
            order.refresh_from_db()
            saved.refresh_from_db()
            self.assertEqual(order.title, 'Delete This Shirt')
            self.assertEqual(order.subtotal, 125000)
            self.assertEqual(order.image, image_url)
            self.assertEqual(saved.image, image_url)
            self.assertTrue(photo.image.storage.exists(photo.image.name))
            self.client.force_login(self.other)
            self.assertEqual(self.client.get(reverse('order_detail', args=[order.pk])).status_code, 200)

    def test_buyer_checkout_handles_a_product_deleted_from_their_bag(self):
        buyer = Client()
        buyer.force_login(self.other)
        buyer.post(reverse('products:bag_add', args=[self.product.slug]))
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.delete_url()).status_code, 302)
        self.assertEqual(cart.items(buyer.session), [])
        response = buyer.get(reverse('transaction:checkout'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('products:home'))


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
