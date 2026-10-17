import re
from smtplib import SMTPException
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from .models import AccountOrder, Profile, WishlistItem

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('keishajanice', 'keisha@example.com', 'Sustainable!2026', first_name='Keisha Janice')
        self.other = User.objects.create_user('other', 'other@example.com', 'Different!2026')
        self.client.force_login(self.user)
        self.order = AccountOrder.objects.create(user=self.user, number='GAIA-1026001', date='2026-10-08', status='in_transit', title='Burberry Trench Coat', size='M', condition='Very good', subtotal=300000, shipping=20000, recipient='Keisha Janice', address='Jakarta')
        self.item = WishlistItem.objects.create(user=self.user, product_key='coat', title='Burberry Trench Coat', size='M', condition='Excellent', price=300000)

    def test_all_account_pages_render(self):
        for name in ['profile', 'edit_profile', 'orders', 'wishlist', 'account_settings', 'password_change']:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'GAIA')
        response = self.client.get(reverse('order_detail', args=[self.order.pk]))
        self.assertContains(response, 'Rp320.000')
        self.assertContains(response, 'In transit')
        for status, label in AccountOrder.Status.choices:
            self.order.status = status
            self.order.save()
            self.assertContains(self.client.get(reverse('order_detail', args=[self.order.pk])), label)

    def test_guest_redirects_to_login_and_can_read_auth_pages(self):
        self.client.logout()
        for name in ['profile', 'edit_profile', 'orders', 'wishlist', 'account_settings', 'password_change']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        for name in ['login', 'register', 'password_reset', 'password_reset_done', 'password_reset_complete']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_email_login_and_validation(self):
        self.client.logout()
        response = self.client.post(reverse('login'), {'username': 'KEISHA@example.com', 'password': 'Sustainable!2026'})
        self.assertRedirects(response, reverse('profile'))
        self.client.logout()
        response = self.client.post(reverse('login'), {'username': 'keisha@example.com', 'password': 'wrong'})
        self.assertContains(response, 'errorlist')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_registration_confirmation_and_email_verification(self):
        self.client.logout()
        data = {'full_name': 'Keisha Janice', 'email': 'new@example.com', 'password1': 'Circular!Fashion2026', 'password2': 'Circular!Fashion2026'}
        response = self.client.post(reverse('register'), data)
        self.assertRedirects(response, reverse('account_created'))
        user = User.objects.get(email='new@example.com')
        self.assertEqual(user.username, 'keishajanice1')
        self.assertTrue(user.check_password(data['password1']))
        self.assertFalse(user.profile.email_verified)
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r'http://testserver(\S+)', mail.outbox[0].body).group(1)
        self.client.get(link)
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.email_verified)
        self.assertContains(self.client.get(reverse('profile')), 'Email verified')

    def test_registration_rejects_duplicates_mismatch_and_weak_passwords(self):
        self.client.logout()
        data = {'full_name': 'New', 'email': 'KEISHA@example.com', 'password1': '123', 'password2': '456'}
        response = self.client.post(reverse('register'), data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.count(), 2)
        self.assertContains(response, 'already exists')
        self.assertContains(response, 'errorlist')

    def test_profile_persists_without_email_mutation(self):
        self.client.get(reverse('profile'))
        response = self.client.post(reverse('edit_profile'), {'full_name': 'Keisha Updated', 'username': 'keishanew', 'email': 'attacker@example.com', 'phone': '+62 812 9876 5432', 'city': 'Bandung', 'country': 'Indonesia'})
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), 'Keisha Updated')
        self.assertEqual(self.user.profile.city, 'Bandung')
        self.assertEqual(self.user.email, 'keisha@example.com')
        self.assertContains(self.client.get(reverse('profile')), 'Bandung')

    def test_profile_rejects_duplicate_username(self):
        self.client.get(reverse('profile'))
        response = self.client.post(reverse('edit_profile'), {'full_name': 'Test', 'username': 'OTHER', 'phone': '', 'city': '', 'country': ''})
        self.assertContains(response, 'already taken')
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'keishajanice')

    def test_wishlist_remove_undo_and_ownership(self):
        remove = reverse('wishlist_remove', args=[self.item.pk])
        self.assertEqual(self.client.get(remove).status_code, 405)
        self.client.post(remove)
        self.item.refresh_from_db()
        self.assertTrue(self.item.removed)
        response = self.client.get(reverse('wishlist'))
        self.assertContains(response, 'No favorites yet')
        self.assertContains(response, 'Undo Removal')
        self.client.post(reverse('wishlist_undo'))
        self.item.refresh_from_db()
        self.assertFalse(self.item.removed)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(remove).status_code, 404)
        session = self.client.session
        session['wishlist_undo'] = self.item.pk
        session.save()
        self.client.post(reverse('wishlist_undo'))
        self.item.refresh_from_db()
        self.assertFalse(self.item.removed)

    def test_orders_are_private(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('order_detail', args=[self.order.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('orders')), self.order.number)
        self.assertContains(self.client.get(reverse('orders')), 'No orders yet')

    def test_password_change_preserves_session(self):
        response = self.client.post(reverse('password_change'), {'old_password': 'Sustainable!2026', 'new_password1': 'Circular!2027Fashion', 'new_password2': 'Circular!2027Fashion'})
        self.assertRedirects(response, reverse('account_settings'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Circular!2027Fashion'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_password_change_rejects_wrong_current_password(self):
        response = self.client.post(reverse('password_change'), {'old_password': 'wrong', 'new_password1': 'Circular!2027Fashion', 'new_password2': 'Circular!2027Fashion'})
        self.assertContains(response, 'errorlist')
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Sustainable!2026'))

    def test_reset_flow_and_single_use_token(self):
        self.client.logout()
        self.assertRedirects(self.client.post(reverse('password_reset'), {'email': self.user.email}), reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        path = re.search(r'http://testserver(\S+)', mail.outbox[0].body).group(1)
        response = self.client.get(path)
        self.assertEqual(response.status_code, 302)
        confirm = response.url
        self.assertContains(self.client.get(confirm), 'Set a new password')
        response = self.client.post(confirm, {'new_password1': 'Reset!Fashion2027', 'new_password2': 'Reset!Fashion2027'})
        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Reset!Fashion2027'))
        self.assertContains(self.client.get(path), 'Link expired')

    def test_unknown_email_reset_has_same_response(self):
        self.client.logout()
        self.assertRedirects(self.client.post(reverse('password_reset'), {'email': 'unknown@example.com'}), reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_logout_is_post_only_and_csrf_protected(self):
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(reverse('logout')).status_code, 403)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_invalid_verification_cannot_verify_user(self):
        Profile.objects.create(user=self.user)
        self.client.get(reverse('verify_email', args=['invalid-token']))
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)

    def test_expired_verification_cannot_verify_user(self):
        Profile.objects.create(user=self.user)
        token = signing.dumps({'user': self.user.pk, 'email': self.user.email}, salt='gaia-email')
        with patch('django.core.signing.time.time', return_value=9999999999):
            self.client.get(reverse('verify_email', args=[token]))
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.email_verified)

    def test_email_failure_does_not_lose_created_account(self):
        self.client.logout()
        with patch('accounts.views.send_mail', side_effect=SMTPException('Mail unavailable')):
            response = self.client.post(reverse('register'), {'full_name': 'New User', 'email': 'new@example.com', 'password1': 'Circular!2026Fashion', 'password2': 'Circular!2026Fashion'})
        self.assertRedirects(response, reverse('account_created'), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse('account_created')), 'could not be sent')
        self.assertNotContains(self.client.get(reverse('account_created')), 'Verification email sent to')
        self.assertTrue(User.objects.filter(email='new@example.com').exists())

    def test_wishlist_mutation_requires_csrf(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(reverse('wishlist_remove', args=[self.item.pk])).status_code, 403)
        self.assertEqual(strict.post(reverse('wishlist_undo')).status_code, 403)
