from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import AccountOrder
from products import cart
from products.models import Product


class SingleItemCheckoutTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = get_user_model().objects.create_user('checkout-seller')
        cls.buyer = get_user_model().objects.create_user('checkout-buyer')
        cls.other_buyer = get_user_model().objects.create_user('checkout-other')
        cls.product = Product.objects.create(seller=cls.seller, title='Single Shirt', price=130000)

    def prepare_checkout(self, client, quantity=1):
        session = client.session
        session['bag'] = {str(self.product.pk): quantity}
        session['transaction_address'] = {
            'recipient': 'Buyer', 'phone': '08123456789', 'address': 'Sample Street',
            'city': 'Depok', 'postal_code': '16424', 'country': 'Indonesia',
        }
        session['transaction_payment'] = 'bank_transfer'
        session.save()

    def test_checkout_reserves_one_item_even_if_an_old_session_has_a_larger_quantity(self):
        self.client.force_login(self.buyer)
        self.prepare_checkout(self.client, quantity=99)
        response = self.client.post(reverse('transaction:confirmation'))
        self.assertEqual(response.status_code, 302)
        order = AccountOrder.objects.get(user=self.buyer)
        self.product.refresh_from_db()
        self.assertEqual(order.subtotal, 130000)
        self.assertEqual(order.product_id, self.product.pk)
        self.assertEqual(order.seller_id, self.seller.pk)
        self.assertEqual(order.status, AccountOrder.Status.AWAITING_PAYMENT)
        self.assertEqual(self.product.status, Product.Status.SOLD)
        self.assertNotIn('bag', self.client.session)
        self.assertTrue(self.seller.products.filter(pk=self.product.pk).exists())

    def test_refresh_and_repeated_confirmation_do_not_create_duplicate_orders(self):
        self.client.force_login(self.buyer)
        self.prepare_checkout(self.client)
        self.client.post(reverse('transaction:confirmation'))
        self.assertEqual(self.client.get(reverse('transaction:confirmation')).status_code, 200)
        self.assertEqual(self.client.post(reverse('transaction:confirmation')).status_code, 200)
        self.assertEqual(AccountOrder.objects.filter(product=self.product).count(), 1)

    def test_second_buyer_cannot_purchase_a_product_already_reserved_by_the_first(self):
        other = Client()
        other.force_login(self.other_buyer)
        self.prepare_checkout(other)
        self.client.force_login(self.buyer)
        self.prepare_checkout(self.client)
        self.client.post(reverse('transaction:confirmation'))
        response = other.post(reverse('transaction:confirmation'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(AccountOrder.objects.filter(user=self.other_buyer).exists())
        self.assertEqual(AccountOrder.objects.filter(product=self.product).count(), 1)
        self.assertEqual(cart.items(other.session), [])

    def test_availability_is_rechecked_after_a_stale_cart_was_read(self):
        self.client.force_login(self.buyer)
        self.prepare_checkout(self.client)
        stale_items = cart.items(self.client.session)
        Product.objects.filter(pk=self.product.pk).update(status=Product.Status.SOLD)
        with patch('transaction.views.cart.items', return_value=stale_items):
            response = self.client.post(reverse('transaction:confirmation'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('transaction:checkout'))
        self.assertFalse(AccountOrder.objects.exists())

    def test_confirmation_preview_does_not_create_an_order_or_mark_an_item_sold(self):
        self.client.force_login(self.buyer)
        self.prepare_checkout(self.client)
        self.assertEqual(self.client.get(reverse('transaction:confirmation')).status_code, 200)
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.AVAILABLE)
        self.assertFalse(AccountOrder.objects.exists())

    def test_order_is_rolled_back_if_reserving_the_product_fails(self):
        self.client.force_login(self.buyer)
        self.prepare_checkout(self.client)
        with patch('transaction.views.Product.save', side_effect=IntegrityError('Reservation failed')):
            with self.assertRaises(IntegrityError):
                self.client.post(reverse('transaction:confirmation'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.status, Product.Status.AVAILABLE)
        self.assertFalse(AccountOrder.objects.exists())

    def test_product_deleted_after_reading_the_cart_cannot_be_ordered(self):
        self.client.force_login(self.buyer)
        self.prepare_checkout(self.client)
        stale_items = cart.items(self.client.session)
        self.product.delete()
        with patch('transaction.views.cart.items', return_value=stale_items):
            response = self.client.post(reverse('transaction:confirmation'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('transaction:checkout'))
        self.assertFalse(AccountOrder.objects.exists())

    def test_order_history_stays_accessible_when_the_public_product_is_sold(self):
        self.client.force_login(self.buyer)
        self.prepare_checkout(self.client)
        self.client.post(reverse('transaction:confirmation'))
        order = AccountOrder.objects.get(user=self.buyer)
        self.assertEqual(self.client.get(reverse('products:detail', args=[self.product.slug])).status_code, 404)
        self.assertEqual(self.client.get(reverse('order_detail', args=[order.pk])).status_code, 200)
        self.assertEqual(order.title, 'Single Shirt')

    def test_confirmation_still_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        self.prepare_checkout(client)
        self.assertEqual(client.post(reverse('transaction:confirmation')).status_code, 403)
        self.assertFalse(AccountOrder.objects.exists())
