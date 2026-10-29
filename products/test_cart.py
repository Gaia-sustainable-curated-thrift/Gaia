from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from . import cart
from .models import Product


AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class BagAvailabilityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = get_user_model().objects.create_user('bag-seller')
        cls.product = Product.objects.create(seller=cls.seller, title='Linen Shirt', price=150000)

    def add(self, **extra):
        return self.client.post(reverse('products:bag_add', args=[self.product.slug]), **extra)

    def set_quantity(self, quantity, **extra):
        return self.client.post(reverse('products:bag_set', args=[self.product.slug]), {'quantity': quantity}, **extra)

    def mark_sold(self):
        self.product.status = Product.Status.SOLD
        self.product.save(update_fields=['status'])

    def test_sold_product_cannot_be_added_by_ajax(self):
        self.mark_sold()
        response = self.add(**AJAX)
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['ok'])
        self.assertEqual(response.json()['bag_count'], 0)
        self.assertEqual(response.json()['toast']['kind'], 'error')
        self.assertEqual(cart.quantity_for(self.client.session, self.product.pk), 0)
        self.assertNotIn('bag_toast', self.client.session)

    def test_non_ajax_rejection_shows_an_error_once(self):
        self.mark_sold()
        response = self.add()
        self.assertEqual(response.status_code, 302)
        page = self.client.get(response.url)
        self.assertContains(page, 'This item is no longer available.')
        self.assertContains(page, 'role="alert"')
        self.assertEqual(cart.count(self.client.session), 0)
        self.assertNotContains(self.client.get(response.url), 'toast toast--error')

    def test_rejected_add_preserves_the_existing_quantity(self):
        self.add()
        self.add()
        self.mark_sold()
        response = self.add(**AJAX)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['bag_count'], 2)
        self.assertEqual(cart.quantity_for(self.client.session, self.product.pk), 2)

    def test_sold_item_can_be_removed_but_not_increased(self):
        self.add()
        self.mark_sold()
        response = self.set_quantity(2, **AJAX)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.json()['open'])
        self.assertIn('Remove unavailable item', response.json()['drawer'])
        self.assertEqual(cart.quantity_for(self.client.session, self.product.pk), 1)
        response = self.set_quantity(0, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['bag_count'], 0)

    def test_invalid_quantity_does_not_silently_change_the_bag(self):
        self.add()
        self.add()
        for value in ['abc', '1.5', '']:
            with self.subTest(quantity=value):
                response = self.set_quantity(value, **AJAX)
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.json()['ok'])
                self.assertEqual(response.json()['bag_count'], 2)
                self.assertEqual(cart.quantity_for(self.client.session, self.product.pk), 2)

    def test_non_ajax_invalid_quantity_keeps_the_drawer_open(self):
        self.add()
        response = self.set_quantity('bad')
        page = self.client.get(response.url)
        self.assertContains(page, 'Enter a valid whole-number quantity.')
        self.assertContains(page, 'data-bag-open')
        self.assertEqual(cart.quantity_for(self.client.session, self.product.pk), 1)

    def test_undo_does_not_restore_a_sold_item(self):
        self.add()
        self.set_quantity(0)
        self.mark_sold()
        response = self.client.post(reverse('products:bag_undo'), **AJAX)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['bag_count'], 0)
        self.assertNotIn('bag_undo', self.client.session)

    def test_undo_handles_a_product_deleted_after_removal(self):
        self.add()
        self.set_quantity(0)
        self.product.delete()
        response = self.client.post(reverse('products:bag_undo'), **AJAX)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['bag_count'], 0)
        self.assertEqual(cart.count(self.client.session), 0)

    def test_undo_without_an_entry_is_a_no_op(self):
        response = self.client.post(reverse('products:bag_undo'), **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['bag_count'], 0)
        self.assertIsNone(response.json()['toast'])

    def test_quantity_limit_and_removing_an_absent_item(self):
        response = self.set_quantity(0, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['toast'])
        response = self.set_quantity(1000000, **AJAX)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['bag_count'], cart.MAX_QUANTITY)

    def test_bag_mutations_require_post_and_csrf(self):
        add_url = reverse('products:bag_add', args=[self.product.slug])
        set_url = reverse('products:bag_set', args=[self.product.slug])
        for url in [add_url, set_url, reverse('products:bag_undo')]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
                self.assertEqual(Client(enforce_csrf_checks=True).post(url).status_code, 403)
        self.assertEqual(cart.count(self.client.session), 0)

    def test_redirect_back_accepts_local_paths_but_rejects_other_hosts(self):
        url = reverse('products:bag_add', args=[self.product.slug])
        for target in ['https://other.example/', '//other.example/']:
            with self.subTest(target=target):
                response = self.client.post(url, {'next': target})
                self.assertEqual(response.url, reverse('products:detail', args=[self.product.slug]))
        response = self.client.post(url, {'next': '/products/picked/'})
        self.assertEqual(response.url, '/products/picked/')


class CartStateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seller = get_user_model().objects.create_user('cart-seller')
        cls.product = Product.objects.create(seller=seller, title='Coat', price=300000)

    def test_malformed_session_containers_are_treated_as_empty(self):
        session = self.client.session
        for value in [None, 'invalid', ['invalid']]:
            with self.subTest(value=value):
                session['bag'] = value
                self.assertEqual(cart.items(session), [])
                self.assertEqual(cart.count(session), 0)

    def test_invalid_quantities_and_missing_products_are_skipped(self):
        session = self.client.session
        session['bag'] = {
            str(self.product.pk): '2',
            'bad-quantity': 'not-a-number',
            'non-numeric-id': 3,
            '999999': 1,
            'negative': -1,
            'zero': 0,
        }
        self.assertEqual(cart.count(session), 2)
        self.assertEqual(cart.subtotal(session), 600000)
        self.assertEqual(cart.items(session)[0]['product'], self.product)

    def test_add_and_set_respect_the_quantity_limit(self):
        session = self.client.session
        cart.add(session, self.product.pk, quantity=1000000)
        cart.add(session, self.product.pk)
        self.assertEqual(cart.quantity_for(session, self.product.pk), cart.MAX_QUANTITY)
        cart.set_quantity(session, self.product.pk, 3)
        self.assertEqual(cart.subtotal(session), 900000)
        cart.set_quantity(session, self.product.pk, 0)
        self.assertNotIn('bag', session)

    def test_deleted_products_do_not_appear_in_the_bag(self):
        session = self.client.session
        cart.add(session, self.product.pk)
        self.product.delete()
        self.assertEqual(cart.items(session), [])
        self.assertEqual(cart.count(session), 0)
