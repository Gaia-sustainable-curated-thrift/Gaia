from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import AccountOrder
from . import cart
from .models import Category, Product


class SoftDeleteListingTests(TestCase):
    ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('soft-owner')
        cls.other = get_user_model().objects.create_user('soft-other')
        women = Category.objects.create(name='Women')
        cls.tops = Category.objects.create(name='Tops', parent=women)

    def setUp(self):
        cache.clear()
        self.product = Product.objects.create(seller=self.owner, title='Soft Coat', price=150000, category=self.tops)
        self.photo = self.product.images.create(image='products/soft.png', is_primary=True)
        self.delete_url = reverse('products:delete', args=[self.product.slug])
        self.restore_url = reverse('products:restore', args=[self.product.slug])

    def delete(self, **extra):
        self.client.force_login(self.owner)
        return self.client.post(self.delete_url, **extra)

    # ----- delete = hide, not erase -----

    def test_delete_only_marks_the_listing_and_keeps_the_row_and_photos(self):
        before = timezone.now()
        self.delete()
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        stored = Product.all_objects.get(pk=self.product.pk)
        self.assertGreaterEqual(stored.deleted_at, before)
        self.assertTrue(stored.images.filter(pk=self.photo.pk).exists())

    def test_deleted_listing_disappears_everywhere_in_the_shop(self):
        self.delete()
        guest = Client()
        for name in ['products:home', 'products:picked', 'products:listing']:
            args = ['women'] if name == 'products:listing' else []
            with self.subTest(page=name):
                self.assertNotContains(guest.get(reverse(name, args=args)), 'Soft Coat')
        self.assertNotContains(guest.get(reverse('products:search'), {'q': 'soft'}), 'Soft Coat')
        self.assertEqual(guest.get(reverse('products:detail', args=[self.product.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse('products:detail', args=[self.product.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse('products:edit', args=[self.product.slug])).status_code, 404)
        self.assertEqual(guest.post(reverse('products:bag_add', args=[self.product.slug])).status_code, 404)
        self.assertFalse(self.owner.products.filter(pk=self.product.pk).exists())

    def test_it_leaves_other_peoples_bags_and_wishlists_alone_but_unreachable(self):
        buyer = Client()
        buyer.post(reverse('products:bag_add', args=[self.product.slug]))
        self.assertEqual(cart.count(buyer.session), 1)
        self.delete()
        self.assertEqual(cart.count(buyer.session), 0)

    def test_order_history_still_points_at_the_deleted_listing(self):
        order = AccountOrder.objects.create(
            user=self.other, number='SOFT-1', date=timezone.localdate(), status='completed',
            product=self.product, seller=self.owner, title=self.product.title,
            subtotal=150000, recipient='Buyer', address='Jakarta',
        )
        self.delete()
        order.refresh_from_db()
        self.assertEqual(order.product_id, self.product.pk)
        self.assertEqual(order.product.title, 'Soft Coat')
        self.client.force_login(self.other)
        self.assertContains(self.client.get(reverse('orders')), 'Soft Coat')

    def test_a_new_listing_can_reuse_the_title_of_a_deleted_one(self):
        self.delete()
        again = Product.objects.create(seller=self.owner, title='Soft Coat', price=99000)
        self.assertNotEqual(again.slug, self.product.slug)
        self.assertTrue(again.slug.startswith('soft-coat'))

    def test_admin_still_lists_deleted_listings(self):
        self.delete()
        admin = get_user_model().objects.create_superuser('soft-admin', 'a@example.test', 'pw')
        self.client.force_login(admin)
        self.assertContains(self.client.get('/admin/products/product/'), 'Soft Coat')

    # ----- Undo -----

    def test_ajax_delete_offers_an_undo_link(self):
        toast = self.delete(**self.ajax).json()['toast']
        self.assertEqual(toast['undo_url'], self.restore_url)
        self.assertTrue(toast['undo_reload'])

    def test_plain_delete_shows_an_undo_button_on_the_next_page(self):
        response = self.delete()
        page = self.client.get(response.url)
        self.assertContains(page, 'Listing deleted.')
        self.assertContains(page, f'action="{self.restore_url}"')
        self.assertContains(page, '>Undo</button>')
        self.assertContains(page, 'data-toast-duration="8000"')

    def test_restore_brings_the_listing_back_with_its_photos(self):
        self.delete()
        response = self.client.post(self.restore_url)
        self.assertRedirects(response, reverse('products:detail', args=[self.product.slug]), fetch_redirect_response=False)
        restored = Product.objects.get(pk=self.product.pk)
        self.assertIsNone(restored.deleted_at)
        self.assertEqual(restored.images.count(), 1)
        self.assertContains(self.client.get(response.url), 'Listing restored.')
        self.assertContains(Client().get(reverse('products:home')), 'Soft Coat')

    def test_ajax_restore_answers_with_the_listing_address(self):
        self.delete()
        data = self.client.post(self.restore_url, **self.ajax).json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['redirect_url'], reverse('products:detail', args=[self.product.slug]))

    def test_only_the_owner_can_restore(self):
        self.delete()
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.restore_url).status_code, 404)
        self.assertEqual(Client().post(self.restore_url).status_code, 302)  # guests go to login
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())

    def test_a_listing_that_was_not_deleted_cannot_be_restored(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.restore_url).status_code, 404)

    def test_restore_only_accepts_post(self):
        self.delete()
        self.assertEqual(self.client.get(self.restore_url).status_code, 405)

    # ----- model -----

    def test_soft_delete_and_restore_on_the_model(self):
        self.product.soft_delete()
        self.assertIsNotNone(Product.all_objects.get(pk=self.product.pk).deleted_at)
        Product.all_objects.get(pk=self.product.pk).restore()
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())
