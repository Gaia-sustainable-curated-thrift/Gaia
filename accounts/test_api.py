from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from products.models import Product
from .models import AccountOrder, AccountRateLimit, Profile, WishlistItem


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MobileAccountAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('buyer', 'buyer@example.com', 'StrongPass!8462')
        Profile.objects.create(user=self.user, phone='+628123456789', city='Depok', country='Indonesia')
        self.other = get_user_model().objects.create_user('seller', 'seller@example.com', 'StrongPass!1239')
        self.product = Product.objects.create(seller=self.other, title='Jacket', price=125000)
        self.client = APIClient()

    def auth(self):
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        return token

    def test_register_reuses_web_validation_and_returns_real_account(self):
        response = self.client.post('/api/accounts/register/', {
            'full_name': 'Mobile Buyer', 'email': 'mobile@example.com',
            'password1': 'UniqueStrong!9864', 'password2': 'UniqueStrong!9864',
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(get_user_model().objects.filter(email='mobile@example.com').exists())
        self.assertTrue(Token.objects.filter(key=response.data['token']).exists())
        self.assertNotIn('password', response.data['user'])
        self.assertNotIn('sessionid', response.cookies)
        duplicate = self.client.post('/api/accounts/register/', {
            'full_name': 'Other', 'email': 'MOBILE@example.com',
            'password1': 'UniqueStrong!9864', 'password2': 'UniqueStrong!9864',
        }, format='json')
        self.assertEqual(duplicate.status_code, 400)

    def test_login_supports_web_email_and_username_and_logout_revokes(self):
        for identity in ('BUYER@example.com', 'buyer'):
            response = self.client.post('/api/accounts/login/', {
                'username': identity, 'password': 'StrongPass!8462',
            }, format='json')
            self.assertEqual(response.status_code, 200, response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {response.data["token"]}')
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 200)
        self.assertEqual(self.client.post('/api/accounts/logout/').status_code, 204)
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 401)

    def test_private_endpoints_reject_guests_even_with_browser_session(self):
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 401)
        self.assertEqual(self.client.get('/api/accounts/wishlist/').status_code, 401)
        self.client.force_login(self.user)
        self.assertEqual(self.client.patch('/api/accounts/me/', {'city': 'Other'}, format='json').status_code, 401)

    def test_profile_patch_is_own_user_and_email_is_immutable(self):
        self.auth()
        response = self.client.patch('/api/accounts/me/', {
            'full_name': 'Updated Buyer', 'username': 'updatedbuyer',
            'phone': '+62 8123456789', 'city': 'Jakarta', 'country': 'Indonesia',
            'email': 'changed@example.com', 'id': self.other.pk,
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated Buyer')
        self.assertEqual(self.user.email, 'buyer@example.com')
        self.assertEqual(self.user.profile.city, 'Jakarta')
        self.assertEqual(self.client.patch('/api/accounts/me/', {'phone': 'invalid'}, format='json').status_code, 400)

    def test_wishlist_shares_web_rows_paginates_and_enforces_ownership(self):
        self.auth()
        response = self.client.post(f'/api/accounts/wishlist/products/{self.product.pk}/')
        self.assertEqual(response.status_code, 200)
        pk = response.data['id']
        self.assertTrue(WishlistItem.objects.filter(user=self.user, product_key=self.product.slug, removed=False).exists())
        self.assertEqual(self.client.get('/api/accounts/wishlist/').data['count'], 1)
        self.assertEqual(self.client.delete(f'/api/accounts/wishlist/{pk}/').status_code, 204)
        self.assertEqual(self.client.get('/api/accounts/wishlist/').data['count'], 0)
        self.assertEqual(self.client.post(f'/api/accounts/wishlist/{pk}/restore/').status_code, 200)
        foreign = WishlistItem.objects.create(user=self.other, product_key='foreign', title='Private', price=1)
        self.assertEqual(self.client.delete(f'/api/accounts/wishlist/{foreign.pk}/').status_code, 404)
        self.product.status = Product.Status.SOLD
        self.product.save()
        self.assertEqual(self.client.get('/api/accounts/wishlist/').data['count'], 0)

    def test_password_change_and_web_password_reset_revoke_tokens(self):
        self.auth()
        bad = self.client.post('/api/accounts/password/change/', {
            'old_password': 'wrong', 'new_password1': 'NewStrong!8462', 'new_password2': 'NewStrong!8462',
        }, format='json')
        self.assertEqual(bad.status_code, 400)
        response = self.client.post('/api/accounts/password/change/', {
            'old_password': 'StrongPass!8462', 'new_password1': 'NewStrong!8462', 'new_password2': 'NewStrong!8462',
        }, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 401)
        self.auth()
        self.user.set_password('ResetFromWeb!5378')
        self.user.save()
        self.assertEqual(self.client.get('/api/accounts/me/').status_code, 401)

    def test_login_rate_limit_cannot_be_bypassed_with_username_email(self):
        for n in range(10):
            identity = 'buyer' if n % 2 else 'BUYER@example.com'
            self.assertEqual(self.client.post('/api/accounts/login/', {'username': identity, 'password': 'wrong'}, format='json').status_code, 400)
        response = self.client.post('/api/accounts/login/', {'username': 'buyer', 'password': 'StrongPass!8462'}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_reset_response_does_not_enumerate_accounts(self):
        known = self.client.post('/api/accounts/password/reset/', {'email': 'buyer@example.com'}, format='json')
        unknown = self.client.post('/api/accounts/password/reset/', {'email': 'unknown@example.com'}, format='json')
        self.assertEqual(known.status_code, 200)
        self.assertEqual(known.data, unknown.data)

    @patch('accounts.api_views._send_verification_email', side_effect=OSError)
    def test_verification_delivery_failure_and_cooldown(self, send):
        self.auth()
        self.assertEqual(self.client.post('/api/accounts/verify/resend/').status_code, 503)
        send.side_effect = None
        send.return_value = False
        self.assertEqual(self.client.post('/api/accounts/verify/resend/').status_code, 429)

    def test_delete_requires_password_confirmation_and_no_pending_orders(self):
        self.auth()
        data = {'password': 'StrongPass!8462', 'confirmation': 'DELETE', 'acknowledge': True}
        self.assertEqual(self.client.delete('/api/accounts/me/', {**data, 'password': 'wrong'}, format='json').status_code, 400)
        order = AccountOrder.objects.create(
            user=self.user, number='PENDING', date='2026-11-20', status='awaiting_payment',
            title='Jacket', subtotal=100, recipient='Buyer', address='Depok',
        )
        self.assertEqual(self.client.delete('/api/accounts/me/', data, format='json').status_code, 400)
        order.status = 'completed'
        order.save()
        self.assertEqual(self.client.delete('/api/accounts/me/', data, format='json').status_code, 204)
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())
