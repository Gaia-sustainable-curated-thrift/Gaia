"""User module unit and request tests; run with python manage.py test accounts.

Uses an isolated test database and in-memory emails; no live OAuth or SMTP.
"""

import re
from datetime import date
from io import StringIO
from pathlib import Path
from smtplib import SMTPException
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail, signing
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from .context_processors import social_login
from .forms import EmailAuthenticationForm, ProfileForm, RegisterForm
from .models import AccountOrder, Profile, WishlistItem
from .templatetags.account_tags import initials, rupiah

User = get_user_model()
PASSWORD = 'Circular!Fashion2026'
TEST_GOOGLE = {'google': {
    'APP': {'client_id': 'test-client', 'secret': 'test-secret'},
    'SCOPE': ['profile', 'email'],
}}


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


class GoogleCallbackProtocolTests(SimpleTestCase):
    @override_settings(ACCOUNT_DEFAULT_HTTP_PROTOCOL='https')
    def test_pws_http_proxy_still_generates_https_callback(self):
        from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
        request = RequestFactory().get('/', HTTP_HOST='danar-iqbal-gaia.pws.cs.ui.ac.id')
        self.assertFalse(request.is_secure())
        callback = GoogleOAuth2Adapter(request).get_callback_url(request, app=None)
        self.assertEqual(callback, 'https://danar-iqbal-gaia.pws.cs.ui.ac.id/accounts/google/login/callback/')

    @override_settings(ACCOUNT_DEFAULT_HTTP_PROTOCOL='http')
    def test_local_development_keeps_http_callback(self):
        from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
        request = RequestFactory().get('/', HTTP_HOST='localhost:8000')
        callback = GoogleOAuth2Adapter(request).get_callback_url(request, app=None)
        self.assertEqual(callback, 'http://localhost:8000/accounts/google/login/callback/')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AccountFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('keishajanice', 'keisha@example.com', 'Sustainable!2026', first_name='Keisha Janice')
        self.other = User.objects.create_user('other', 'other@example.com', 'Different!2026')
        self.client.force_login(self.user)
        self.order = AccountOrder.objects.create(user=self.user, number='GAIA-1026001', date='2026-10-08', status='in_transit', title='Burberry Trench Coat', condition='Very good', subtotal=300000, shipping=20000, recipient='Keisha Janice', address='Jakarta')
        self.item = WishlistItem.objects.create(user=self.user, product_key='coat', title='Burberry Trench Coat', condition='Excellent', price=300000)

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


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PwsRegistrationCsrfTests(TestCase):
    host = 'danar-iqbal-gaia.pws.cs.ui.ac.id'
    origin = f'https://{host}'

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.client.get(reverse('register'), HTTP_HOST=self.host)
        self.token = self.client.cookies['csrftoken'].value
        self.data = {
            'full_name': 'PWS Test User',
            'email': 'pws-test@example.com',
            'password1': 'Circular!Fashion2026',
            'password2': 'Circular!Fashion2026',
        }

    def test_https_origin_registration_through_http_proxy(self):
        response = self.client.post(
            reverse('register'), {**self.data, 'csrfmiddlewaretoken': self.token},
            HTTP_HOST=self.host, HTTP_ORIGIN=self.origin,
        )
        self.assertRedirects(response, reverse('account_created'), fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(email=self.data['email']).exists())

    def test_trusted_origin_still_requires_csrf_token(self):
        response = self.client.post(
            reverse('register'), self.data,
            HTTP_HOST=self.host, HTTP_ORIGIN=self.origin,
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_untrusted_origin_is_rejected_with_valid_token(self):
        response = self.client.post(
            reverse('register'), {**self.data, 'csrfmiddlewaretoken': self.token},
            HTTP_HOST=self.host, HTTP_ORIGIN='https://untrusted.example',
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.exists())


class FormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('gaia', 'gaia@example.com', PASSWORD, first_name='Gaia')
        Profile.objects.create(user=cls.user, city='Jakarta')

    def registration(self, **changes):
        data = {'full_name': 'New User', 'email': 'new@example.com',
                'password1': PASSWORD, 'password2': PASSWORD}
        data.update(changes)
        return RegisterForm(data)

    def profile_form(self, **changes):
        data = {'full_name': 'Gaia Updated', 'username': 'gaia', 'phone': '+62 81234567890',
                'city': 'Bandung', 'country': 'Indonesia', 'email': 'forged@example.com'}
        data.update(changes)
        return ProfileForm(data, instance=self.user)

    def test_registration_normalizes_email_and_hashes_password(self):
        form = self.registration(email='NEW@example.com')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, 'new@example.com')
        self.assertEqual(user.username, 'newuser')
        self.assertEqual(user.first_name, 'New User')
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.check_password(PASSWORD))

    def test_registration_resolves_multiple_username_collisions(self):
        User.objects.create_user('newuser')
        User.objects.create_user('newuser1')
        form = self.registration()
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().username, 'newuser2')

    def test_registration_commit_false_and_empty_slug_fallback(self):
        form = self.registration(full_name='!!!')
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save(commit=False)
        self.assertIsNone(user.pk)
        self.assertEqual(user.username, 'gaia1')
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(User.objects.filter(email='new@example.com').exists())

    def test_registration_rejects_duplicate_email(self):
        form = self.registration(email='GAIA@example.com')
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_registration_rejects_invalid_fields_and_passwords(self):
        for changes, field in [({'full_name': ''}, 'full_name'),
                               ({'email': 'invalid'}, 'email'),
                               ({'password2': 'Different!2026'}, 'password2'),
                               ({'password1': '123', 'password2': '123'}, 'password2')]:
            with self.subTest(changes=changes):
                form = self.registration(**changes)
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)

    def test_login_accepts_username_and_case_insensitive_email(self):
        for identifier in ['gaia', 'GAIA@example.com']:
            with self.subTest(identifier=identifier):
                form = EmailAuthenticationForm(data={'username': identifier, 'password': PASSWORD})
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.get_user().pk, self.user.pk)

    def test_login_rejects_wrong_password_and_unknown_email(self):
        for identifier, password in [('gaia', 'wrong'), ('missing@example.com', PASSWORD)]:
            with self.subTest(identifier=identifier):
                form = EmailAuthenticationForm(data={'username': identifier, 'password': password})
                self.assertFalse(form.is_valid())
                self.assertTrue(form.non_field_errors())

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        form = EmailAuthenticationForm(data={'username': 'gaia', 'password': PASSWORD})
        self.assertFalse(form.is_valid())

    def test_profile_saves_both_models_and_ignores_forged_email(self):
        form = self.profile_form()
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        user.refresh_from_db()
        self.assertEqual(user.get_full_name(), 'Gaia Updated')
        self.assertEqual(user.email, 'gaia@example.com')
        self.assertEqual(user.profile.city, 'Bandung')
        self.assertEqual(user.profile.country, 'Indonesia')
        self.assertEqual(user.profile.phone, '+62 81234567890')

    def test_profile_commit_false_does_not_persist_either_model(self):
        form = self.profile_form()
        self.assertTrue(form.is_valid(), form.errors)
        pending = form.save(commit=False)
        self.assertEqual(pending.first_name, 'Gaia Updated')
        stored = User.objects.get(pk=self.user.pk)
        self.assertEqual(stored.first_name, 'Gaia')
        self.assertEqual(stored.profile.city, 'Jakarta')

    def test_profile_rejects_other_username_but_allows_own(self):
        User.objects.create_user('taken')
        form = self.profile_form(username='TAKEN')
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)
        own = self.profile_form()
        self.assertTrue(own.is_valid(), own.errors)


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SOCIALACCOUNT_PROVIDERS=TEST_GOOGLE,
)
class UserViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('owner', 'owner@example.com', PASSWORD, first_name='Owner')
        cls.other = User.objects.create_user('other', 'other@example.com', PASSWORD)
        cls.order = AccountOrder.objects.create(
            user=cls.user, number='GAIA-TEST-1', date=date(2026, 10, 8),
            status='in_transit', title='Coat', subtotal=300000, shipping=20000,
            recipient='Owner', address='Jakarta',
        )
        cls.item = WishlistItem.objects.create(user=cls.user, product_key='coat', title='Coat', price=300000)

    def setUp(self):
        self.client.force_login(self.user)

    def register_data(self):
        return {'full_name': 'New Member', 'email': 'new@example.com',
                'password1': PASSWORD, 'password2': PASSWORD}

    def test_account_pages_and_order_statuses(self):
        for name in ['profile', 'edit_profile', 'orders', 'wishlist', 'account_settings', 'password_change', 'account_created']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        for status, label in AccountOrder.Status.choices:
            self.order.status = status
            self.order.save()
            response = self.client.get(reverse('order_detail', args=[self.order.pk]))
            self.assertContains(response, label)
            self.assertContains(response, 'Rp320.000')

    def test_guest_cannot_access_private_pages_or_mutations(self):
        self.client.logout()
        for name in ['profile', 'edit_profile', 'orders', 'wishlist', 'account_settings', 'password_change', 'account_created']:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse('login') + '?next='))
        for url in [reverse('wishlist_remove', args=[self.item.pk]), reverse('wishlist_undo')]:
            self.assertEqual(self.client.post(url).status_code, 302)

    def test_guest_auth_pages_and_login_redirect(self):
        self.client.logout()
        for name in ['register', 'login', 'password_reset', 'password_reset_done', 'password_reset_complete']:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        response = self.client.post(reverse('login'), {'username': 'OWNER@example.com', 'password': PASSWORD})
        self.assertRedirects(response, reverse('profile'))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_authenticated_registration_redirects_without_creating_user(self):
        before = User.objects.count()
        for method in [self.client.get, self.client.post]:
            self.assertRedirects(method(reverse('register')), reverse('profile'))
        self.assertEqual(User.objects.count(), before)

    def test_registration_creates_profile_session_and_verifiable_email(self):
        self.client.logout()
        response = self.client.post(reverse('register'), self.register_data())
        self.assertRedirects(response, reverse('account_created'))
        user = User.objects.get(email='new@example.com')
        self.assertFalse(user.profile.email_verified)
        self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)
        self.assertTrue(self.client.session['verification_email_sent'])
        self.assertEqual(mail.outbox[0].to, [user.email])
        link = re.search(r'http://testserver(\S+)', mail.outbox[0].body).group(1)
        self.client.get(link)
        user.profile.refresh_from_db()
        self.assertTrue(user.profile.email_verified)

    def test_invalid_registration_does_not_create_account(self):
        self.client.logout()
        data = self.register_data()
        data['password2'] = 'Different!2026'
        response = self.client.post(reverse('register'), data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('password2', response.context['form'].errors)
        self.assertFalse(User.objects.filter(email=data['email']).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_email_delivery_failure_keeps_created_account(self):
        self.client.logout()
        for error in [SMTPException('SMTP unavailable'), OSError('Connection unavailable')]:
            with self.subTest(error=type(error).__name__):
                data = self.register_data()
                data['email'] = type(error).__name__.lower() + '@example.com'
                with patch('accounts.views.send_mail', side_effect=error):
                    response = self.client.post(reverse('register'), data)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(User.objects.filter(email=data['email']).exists())
                self.assertFalse(self.client.session['verification_email_sent'])
                self.assertContains(self.client.get(reverse('account_created')), 'could not be sent')
                self.client.logout()

    def test_registration_rolls_back_user_when_profile_creation_fails(self):
        self.client.logout()
        with patch('accounts.views.Profile.objects.create', side_effect=IntegrityError('profile failure')):
            with self.assertRaises(IntegrityError):
                self.client.post(reverse('register'), self.register_data())
        self.assertFalse(User.objects.filter(email='new@example.com').exists())

    def test_profile_context_counts_only_active_owned_items(self):
        WishlistItem.objects.create(user=self.user, product_key='removed', title='Removed', price=1, removed=True)
        WishlistItem.objects.create(user=self.other, product_key='other', title='Other', price=1)
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.context['order_count'], 1)
        self.assertEqual(response.context['wishlist_count'], 1)
        self.assertFalse(response.context['email_verified'])
        self.assertEqual(response.context['profile'].user_id, self.user.pk)
        self.assertEqual(Profile.objects.filter(user=self.user).count(), 1)

    def test_verification_context_supports_local_and_google_verification(self):
        profile = Profile.objects.create(user=self.user, email_verified=True)
        self.assertTrue(self.client.get(reverse('profile')).context['email_verified'])
        profile.email_verified = False
        profile.save()
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True)
        self.assertTrue(self.client.get(reverse('profile')).context['email_verified'])

    def test_invalid_expired_and_changed_email_tokens_do_not_verify(self):
        profile = Profile.objects.create(user=self.user)
        token = signing.dumps({'user': self.user.pk, 'email': self.user.email}, salt='gaia-email')
        self.client.get(reverse('verify_email', args=[token + 'tampered']))
        with patch('django.core.signing.time.time', return_value=9999999999):
            self.client.get(reverse('verify_email', args=[token]))
        profile.refresh_from_db()
        self.assertFalse(profile.email_verified)
        self.user.email = 'changed@example.com'
        self.user.save()
        self.assertEqual(self.client.get(reverse('verify_email', args=[token])).status_code, 404)

    def test_edit_profile_persists_and_rejects_invalid_input(self):
        data = {'full_name': 'Updated Owner', 'username': 'updated', 'phone': '+62812',
                'city': 'Bandung', 'country': 'Indonesia'}
        response = self.client.post(reverse('edit_profile'), data)
        self.assertRedirects(response, reverse('profile'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'updated')
        self.assertEqual(self.user.profile.city, 'Bandung')
        data['username'] = 'other'
        response = self.client.post(reverse('edit_profile'), data)
        self.assertIn('username', response.context['form'].errors)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'updated')

    def test_orders_and_wishlist_are_private(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('order_detail', args=[self.order.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('wishlist_remove', args=[self.item.pk])).status_code, 404)
        self.assertEqual(list(self.client.get(reverse('orders')).context['orders']), [])
        self.assertEqual(list(self.client.get(reverse('wishlist')).context['items']), [])

    def test_wishlist_soft_delete_and_undo(self):
        self.assertEqual(self.client.get(reverse('wishlist_remove', args=[self.item.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse('wishlist_undo')).status_code, 405)
        self.client.post(reverse('wishlist_remove', args=[self.item.pk]))
        self.item.refresh_from_db()
        self.assertTrue(self.item.removed)
        self.assertEqual(self.client.session['wishlist_undo'], self.item.pk)
        self.assertContains(self.client.get(reverse('wishlist')), 'No favorites yet')
        self.client.post(reverse('wishlist_undo'))
        self.item.refresh_from_db()
        self.assertFalse(self.item.removed)
        self.assertNotIn('wishlist_undo', self.client.session)

    def test_undo_without_history_and_forged_foreign_id_are_safe(self):
        self.assertRedirects(self.client.post(reverse('wishlist_undo')), reverse('wishlist'))
        self.item.removed = True
        self.item.save()
        self.client.force_login(self.other)
        session = self.client.session
        session['wishlist_undo'] = self.item.pk
        session.save()
        self.client.post(reverse('wishlist_undo'))
        self.item.refresh_from_db()
        self.assertTrue(self.item.removed)

    def test_password_change_validates_current_password_and_preserves_session(self):
        data = {'old_password': 'wrong', 'new_password1': 'Changed!2026Fashion', 'new_password2': 'Changed!2026Fashion'}
        response = self.client.post(reverse('password_change'), data)
        self.assertIn('old_password', response.context['form'].errors)
        data['old_password'] = PASSWORD
        response = self.client.post(reverse('password_change'), data)
        self.assertRedirects(response, reverse('account_settings'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(data['new_password1']))
        self.assertEqual(int(self.client.session['_auth_user_id']), self.user.pk)

    def test_password_reset_email_and_single_use_token(self):
        self.client.logout()
        self.assertRedirects(self.client.post(reverse('password_reset'), {'email': self.user.email}), reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        path = re.search(r'http://testserver(\S+)', mail.outbox[0].body).group(1)
        confirm = self.client.get(path).url
        self.assertContains(self.client.get(confirm), 'Set a new password')
        response = self.client.post(confirm, {'new_password1': 'Reset!2026Fashion', 'new_password2': 'Reset!2026Fashion'})
        self.assertRedirects(response, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Reset!2026Fashion'))
        self.assertContains(self.client.get(path), 'Link expired')

    def test_unknown_reset_email_does_not_reveal_account_existence(self):
        self.client.logout()
        self.assertRedirects(self.client.post(reverse('password_reset'), {'email': 'unknown@example.com'}), reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_csrf_required_for_logout_and_wishlist(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        for url in [reverse('logout'), reverse('wishlist_remove', args=[self.item.pk]), reverse('wishlist_undo')]:
            with self.subTest(url=url):
                self.assertEqual(strict.post(url).status_code, 403)
        self.assertEqual(self.client.get(reverse('logout')).status_code, 405)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_pws_origin_requires_token_and_rejects_foreign_origin(self):
        strict = Client(enforce_csrf_checks=True)
        host = 'danar-iqbal-gaia.pws.cs.ui.ac.id'
        strict.get(reverse('register'), HTTP_HOST=host)
        token = strict.cookies['csrftoken'].value
        data = self.register_data()
        self.assertEqual(strict.post(reverse('register'), data, HTTP_HOST=host, HTTP_ORIGIN='https://' + host).status_code, 403)
        data['csrfmiddlewaretoken'] = token
        self.assertEqual(strict.post(reverse('register'), data, HTTP_HOST=host, HTTP_ORIGIN='https://foreign.example').status_code, 403)
        response = strict.post(reverse('register'), data, HTTP_HOST=host, HTTP_ORIGIN='https://' + host)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(email=data['email']).exists())


class HelperTests(SimpleTestCase):
    def test_google_button_configuration(self):
        for provider, enabled in [({}, False), ({'google': {'APP': {'client_id': 'id'}}}, False), (TEST_GOOGLE, True)]:
            with self.subTest(enabled=enabled), override_settings(SOCIALACCOUNT_PROVIDERS=provider):
                self.assertEqual(social_login(RequestFactory().get('/')), {'google_login_enabled': enabled})

    def test_rupiah_and_initials(self):
        self.assertEqual(rupiah(300000), 'Rp300.000')
        self.assertEqual(rupiah(0), 'Rp0')
        self.assertEqual(initials(User(first_name='Gaia', last_name='Putri')), 'GP')
        self.assertEqual(initials(User(username='gaia')), 'G')

    def test_callback_protocols(self):
        from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
        for protocol, host in [('https', 'danar-iqbal-gaia.pws.cs.ui.ac.id'), ('http', 'localhost:8000')]:
            with self.subTest(protocol=protocol), override_settings(ACCOUNT_DEFAULT_HTTP_PROTOCOL=protocol):
                request = RequestFactory().get('/', HTTP_HOST=host)
                self.assertEqual(GoogleOAuth2Adapter(request).get_callback_url(request, None), f'{protocol}://{host}/accounts/google/login/callback/')


class ModelAndDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('demo', first_name='Demo')

    def test_wishlist_unique_per_user_and_cascade(self):
        Profile.objects.create(user=self.user)
        WishlistItem.objects.create(user=self.user, product_key='coat', title='Coat', price=10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WishlistItem.objects.create(user=self.user, product_key='coat', title='Duplicate', price=10)
        other = User.objects.create_user('other')
        WishlistItem.objects.create(user=other, product_key='coat', title='Coat', price=10)
        self.user.delete()
        self.assertFalse(Profile.objects.exists())
        self.assertEqual(WishlistItem.objects.count(), 1)

    def test_demo_command_creates_correct_totals_statuses_and_is_idempotent(self):
        for _ in range(2):
            call_command('seed_account_demo', username='demo', stdout=StringIO())
        self.assertEqual(self.user.account_orders.count(), 3)
        self.assertEqual(self.user.wishlist_items.count(), 1)
        self.assertEqual(Profile.objects.filter(user=self.user).count(), 1)
        self.assertEqual(set(self.user.account_orders.values_list('status', flat=True)), set(AccountOrder.Status.values))
        for order in self.user.account_orders.all():
            self.assertEqual(order.total, 320000)
            self.assertEqual(order.recipient, 'Demo')
        self.assertEqual(self.user.account_orders.first().status, AccountOrder.Status.AWAITING_PAYMENT)

    def test_demo_uses_username_fallback_and_rejects_missing_user(self):
        self.user.first_name = ''
        self.user.save()
        call_command('seed_account_demo', username='demo', stdout=StringIO())
        self.assertEqual(self.user.account_orders.first().recipient, 'demo')
        with self.assertRaises(CommandError):
            call_command('seed_account_demo', username='missing', stdout=StringIO())


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    SOCIALACCOUNT_PROVIDERS=TEST_GOOGLE,
    ACCOUNT_DEFAULT_HTTP_PROTOCOL='https',
)
class DeleteAccountTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('delete-owner', 'delete@example.com', PASSWORD)
        cls.other = User.objects.create_user('keep-other', 'keep@example.com', PASSWORD)
        Profile.objects.create(user=cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def data(self, **changes):
        data = {'password': PASSWORD, 'confirmation': 'DELETE', 'acknowledge': 'on'}
        data.update(changes)
        return data

    def google_user(self, verified=True):
        self.user.set_unusable_password()
        self.user.save()
        if verified:
            EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True)
        self.client.force_login(self.user)

    def email_link(self):
        self.client.post(reverse('send_delete_confirmation'))
        return re.search(r'https://testserver(\S+)', mail.outbox[-1].body).group(1)

    def test_settings_links_to_confirmation_and_get_never_deletes(self):
        self.assertContains(self.client.get(reverse('account_settings')), reverse('delete_account'))
        response = self.client.get(reverse('delete_account'))
        self.assertContains(response, 'Before you say goodbye')
        self.assertContains(response, 'Current password')
        self.assertContains(response, 'Keep My Account')
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_guest_and_unsupported_methods(self):
        self.assertEqual(self.client.put(reverse('delete_account')).status_code, 405)
        self.assertEqual(self.client.get(reverse('send_delete_confirmation')).status_code, 405)
        self.client.logout()
        for url in [reverse('delete_account'), reverse('send_delete_confirmation'), reverse('delete_account_confirm', args=['token'])]:
            self.assertEqual(self.client.post(url).status_code, 302)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_invalid_password_phrase_checkbox_and_empty_post(self):
        for data, field in [(self.data(password='wrong'), 'password'),
                            (self.data(confirmation='delete'), 'confirmation'),
                            (self.data(acknowledge=''), 'acknowledge'), ({}, 'password')]:
            with self.subTest(field=field):
                response = self.client.post(reverse('delete_account'), data)
                self.assertIn(field, response.context['form'].errors)
                self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_delete_cascades_own_records_logs_out_and_keeps_other_user(self):
        from products.models import Product
        # All fixtures are created in Django's isolated test database.
        WishlistItem.objects.create(user=self.user, product_key='delete', title='Coat', price=10)
        Product.objects.create(seller=self.user, title='Delete listing', price=10)
        AccountOrder.objects.create(user=self.user, number='DELETE-COMPLETED', date=date(2026, 10, 1), status='completed', title='Coat', subtotal=10, recipient='Owner', address='Jakarta')
        second = Client()
        second.force_login(self.user)
        response = self.client.post(reverse('delete_account'), self.data(user_id=self.other.pk))
        self.assertRedirects(response, reverse('login'))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Profile.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Product.objects.filter(seller_id=self.user.pk).exists())
        self.assertFalse(WishlistItem.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(AccountOrder.objects.filter(user_id=self.user.pk).exists())
        self.assertTrue(User.objects.filter(pk=self.other.pk).exists())
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertEqual(second.get(reverse('profile')).status_code, 302)

    def test_csrf_required_for_local_delete_email_and_email_confirm(self):
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        for url in [reverse('delete_account'), reverse('send_delete_confirmation'), reverse('delete_account_confirm', args=['token'])]:
            self.assertEqual(strict.post(url, self.data()).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_pending_order_blocks_get_and_post(self):
        for status in ['awaiting_payment', 'in_transit']:
            with self.subTest(status=status):
                order = AccountOrder.objects.create(user=self.user, number='BLOCK-' + status, date=date(2026, 10, 1), status=status, title='Coat', subtotal=10, recipient='Owner', address='Jakarta')
                self.assertContains(self.client.get(reverse('delete_account')), 'You still have pending orders')
                response = self.client.post(reverse('delete_account'), self.data())
                self.assertTrue(response.context['form'].non_field_errors())
                self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
                order.delete()

    def test_order_rechecked_inside_transaction(self):
        with patch('accounts.views._deletion_blocked', side_effect=[False, True]):
            response = self.client.post(reverse('delete_account'), self.data())
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_protected_records_show_error_without_logging_out(self):
        from django.db.models.deletion import ProtectedError
        with patch.object(User, 'delete', side_effect=ProtectedError('Retained record', [])):
            response = self.client.post(reverse('delete_account'), self.data())
        self.assertContains(response, 'records that must be retained')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertIn('_auth_user_id', self.client.session)

    def test_password_account_does_not_send_confirmation_email(self):
        self.assertRedirects(self.client.post(reverse('send_delete_confirmation')), reverse('delete_account'))
        self.assertEqual(len(mail.outbox), 0)

    def test_google_direct_delete_is_rejected(self):
        self.google_user()
        self.assertContains(self.client.get(reverse('delete_account')), 'Send Confirmation Email')
        response = self.client.post(reverse('delete_account'), self.data())
        self.assertTrue(response.context['form'].non_field_errors())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_google_email_link_requires_final_post_and_is_one_time(self):
        self.google_user()
        link = self.email_link()
        self.assertEqual(mail.outbox[0].to, [self.user.email])
        self.assertContains(self.client.get(link), 'Email confirmation received')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        response = self.client.post(link, {'confirmation': 'DELETE', 'acknowledge': 'on'})
        self.assertRedirects(response, reverse('login'))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(self.client.post(link, self.data()).status_code, 302)

    def test_google_link_rejects_tampering_expiry_and_different_session(self):
        self.google_user()
        link = self.email_link()
        self.assertContains(self.client.get(link.rstrip('/') + 'invalid/'), 'invalid or expired')
        second = Client()
        second.force_login(self.user)
        response = second.post(link, self.data())
        self.assertTrue(response.context['form'].non_field_errors())
        with patch('accounts.views.time.time', return_value=9999999999):
            response = self.client.post(link, self.data())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_google_link_rejects_other_account_and_changed_email(self):
        self.google_user()
        link = self.email_link()
        self.other.set_unusable_password()
        self.other.save()
        second = Client()
        second.force_login(self.other)
        session = second.session
        session['account_delete_confirmation'] = self.client.session['account_delete_confirmation']
        session.save()
        self.assertTrue(second.post(link, self.data()).context['form'].non_field_errors())
        self.user.email = 'changed@example.com'
        self.user.save()
        self.assertTrue(self.client.post(link, self.data()).context['form'].non_field_errors())
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_email_resend_cooldown_and_new_link_invalidates_previous(self):
        self.google_user()
        old_link = self.email_link()
        self.client.post(reverse('send_delete_confirmation'))
        self.assertEqual(len(mail.outbox), 1)
        session = self.client.session
        pending = session['account_delete_confirmation']
        pending['sent_at'] -= 61
        session['account_delete_confirmation'] = pending
        session.save()
        new_link = self.email_link()
        self.assertNotEqual(old_link, new_link)
        self.assertContains(self.client.get(old_link), 'invalid or expired')
        self.assertContains(self.client.get(new_link), 'Email confirmation received')

    def test_google_email_requires_verified_address_and_no_pending_order(self):
        self.google_user(verified=False)
        self.client.post(reverse('send_delete_confirmation'))
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(self.client.get(reverse('delete_account')), 'A verified email is required')
        AccountOrder.objects.create(user=self.user, number='BLOCK-EMAIL', date=date(2026, 10, 1), status='in_transit', title='Coat', subtotal=10, recipient='Owner', address='Jakarta')
        self.client.post(reverse('send_delete_confirmation'))
        self.assertEqual(len(mail.outbox), 0)

    def test_google_email_failure_does_not_authorize_deletion(self):
        self.google_user()
        for result in [SMTPException('Unavailable'), 0]:
            with self.subTest(result=result):
                kwargs = {'side_effect': result} if isinstance(result, Exception) else {'return_value': result}
                with patch('accounts.views.send_mail', **kwargs):
                    self.client.post(reverse('send_delete_confirmation'))
                self.assertNotIn('account_delete_confirmation', self.client.session)
                self.assertTrue(User.objects.filter(pk=self.user.pk).exists())


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    SOCIALACCOUNT_PROVIDERS=TEST_GOOGLE,
)
class AvatarTests(TestCase):
    def setUp(self):
        import tempfile
        self.media = tempfile.TemporaryDirectory(prefix='gaia-avatar-tests-')
        self.addCleanup(self.media.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create_user('avatar-owner', 'avatar@example.com', PASSWORD, first_name='Avatar')
        Profile.objects.create(user=self.user)
        self.client.force_login(self.user)
        self.data = {'full_name': 'Avatar Owner', 'username': 'avatar-owner', 'phone': '', 'city': 'Jakarta', 'country': 'Indonesia'}

    def image(self, filename='photo.png', format='PNG', size=(100, 80)):
        from PIL import Image
        from io import BytesIO
        from django.core.files.uploadedfile import SimpleUploadedFile
        output = BytesIO()
        Image.new('RGB', size, 'green').save(output, format=format)
        return SimpleUploadedFile(filename, output.getvalue(), content_type='image/' + format.lower())

    def upload(self, photo=None):
        return self.client.post(reverse('edit_profile'), {**self.data, 'avatar': photo or self.image()})

    def test_upload_normalizes_image_and_renders_media_url(self):
        from PIL import Image
        self.assertRedirects(self.upload(), reverse('profile'))
        self.user.profile.refresh_from_db()
        avatar = self.user.profile.avatar
        self.assertTrue(avatar.name.startswith('avatars/'))
        self.assertTrue(avatar.name.endswith('.jpg'))
        with avatar.open('rb') as file:
            with Image.open(file) as image:
                self.assertEqual(image.size, (512, 512))
                self.assertEqual(image.format, 'JPEG')
                self.assertNotIn('exif', image.info)
        response = self.client.get(reverse('profile'))
        self.assertContains(response, avatar.url)
        self.assertNotContains(response, '/static/media/avatars/')
        self.assertContains(self.client.get(reverse('edit_profile')), 'multipart/form-data')

    def test_jpeg_and_webp_uploads_are_supported(self):
        for format, name in [('JPEG', 'photo.jpg'), ('WEBP', 'photo.webp')]:
            with self.subTest(format=format), self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.upload(self.image(name, format)).status_code, 302)

    def test_replace_photo_removes_old_file_after_commit(self):
        self.upload()
        self.user.profile.refresh_from_db()
        old_name = self.user.profile.avatar.name
        storage = self.user.profile.avatar.storage
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.upload().status_code, 302)
            self.assertTrue(storage.exists(old_name))
        self.user.profile.refresh_from_db()
        self.assertNotEqual(self.user.profile.avatar.name, old_name)
        self.assertFalse(storage.exists(old_name))
        self.assertTrue(storage.exists(self.user.profile.avatar.name))

    def test_edit_without_file_keeps_existing_photo(self):
        self.upload()
        self.user.profile.refresh_from_db()
        name = self.user.profile.avatar.name
        response = self.client.post(reverse('edit_profile'), {**self.data, 'city': 'Bandung'})
        self.assertRedirects(response, reverse('profile'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar.name, name)
        self.assertEqual(self.user.profile.city, 'Bandung')

    def test_rejects_non_image_and_gif(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        for file in [SimpleUploadedFile('fake.jpg', b'not an image', content_type='image/jpeg'), self.image('animated.gif', 'GIF')]:
            with self.subTest(name=file.name):
                response = self.upload(file)
                self.assertEqual(response.status_code, 200)
                self.assertIn('avatar', response.context['form'].errors)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)

    def test_rejects_files_above_two_megabytes_and_excessive_dimensions(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        large = SimpleUploadedFile('large.png', self.image().read() + b'x' * (2 * 1024 * 1024), content_type='image/png')
        for file in [large, self.image(size=(4097, 1))]:
            with self.subTest(name=file.name):
                response = self.upload(file)
                self.assertIn('avatar', response.context['form'].errors)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)

    def test_processing_failure_returns_validation_error(self):
        with patch('accounts.forms.ImageOps.exif_transpose', side_effect=OSError('invalid image')):
            response = self.upload()
        self.assertIn('avatar', response.context['form'].errors)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)

    def test_invalid_form_does_not_replace_photo(self):
        self.upload()
        self.user.profile.refresh_from_db()
        name = self.user.profile.avatar.name
        response = self.client.post(reverse('edit_profile'), {**self.data, 'username': '', 'avatar': self.image()})
        self.assertIn('username', response.context['form'].errors)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.avatar.name, name)

    def test_upload_changes_only_current_users_photo(self):
        other = User.objects.create_user('other-avatar')
        Profile.objects.create(user=other)
        self.client.post(reverse('edit_profile'), {**self.data, 'user_id': other.pk, 'avatar': self.image()})
        self.user.profile.refresh_from_db()
        other.profile.refresh_from_db()
        self.assertTrue(self.user.profile.avatar)
        self.assertFalse(other.profile.avatar)

    def test_guest_cannot_upload(self):
        self.client.logout()
        response = self.upload()
        self.assertEqual(response.status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)

    def test_commit_false_does_not_write_avatar(self):
        form = ProfileForm(self.data, {'avatar': self.image()}, instance=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save(commit=False)
        self.user.profile.refresh_from_db()
        self.assertFalse(self.user.profile.avatar)
        self.assertEqual(list(Path(self.media.name).rglob('*')), [])

    def test_deleting_account_removes_photo_after_commit(self):
        self.upload()
        self.user.profile.refresh_from_db()
        avatar = self.user.profile.avatar
        name, storage = avatar.name, avatar.storage
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('delete_account'), {'password': PASSWORD, 'confirmation': 'DELETE', 'acknowledge': 'on'})
            self.assertEqual(response.status_code, 302)
            self.assertTrue(storage.exists(name))
        self.assertFalse(storage.exists(name))
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_storage_cleanup_failure_is_logged_without_undoing_save(self):
        self.upload()
        self.user.profile.refresh_from_db()
        storage = self.user.profile.avatar.storage
        with patch.object(storage, 'delete', side_effect=OSError('storage unavailable')):
            with self.assertLogs('accounts.avatars', level='WARNING'), self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.upload().status_code, 302)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.avatar)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class MyProductsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from products.models import Category, Product
        cls.user = User.objects.create_user('my-listings-owner', 'listings@example.com', PASSWORD)
        cls.other = User.objects.create_user('my-listings-other')
        parent = Category.objects.create(name='My Products Test Parent', slug='my-products-test-parent')
        cls.category = Category.objects.create(name='Test Tops', slug='my-products-test-tops', parent=parent)
        cls.available = Product.objects.create(seller=cls.user, title='My Linen Shirt', price=125000, category=cls.category)
        cls.sold = Product.objects.create(seller=cls.user, title='My Sold Coat', price=250000, status='sold', category=cls.category)
        cls.foreign = Product.objects.create(seller=cls.other, title='Other Seller Secret', price=100000, category=cls.category)

    def setUp(self):
        self.client.force_login(self.user)
        self.url = reverse('my_products')

    def test_guest_must_login_and_post_is_not_allowed(self):
        self.assertEqual(self.client.post(self.url).status_code, 405)
        self.client.logout()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse('login') + '?next='))

    def test_page_contains_only_current_users_products(self):
        response = self.client.get(self.url, {'seller': self.other.pk})
        self.assertContains(response, self.available.title)
        self.assertContains(response, self.sold.title)
        self.assertNotContains(response, self.foreign.title)
        self.assertEqual(response.context['listing_totals'], {'total': 2, 'available': 1, 'sold': 1})
        self.assertEqual(response.context['active'], 'products')
        self.assertContains(response, reverse('products:edit', args=[self.available.slug]))
        self.assertContains(response, reverse('products:delete', args=[self.available.slug]))
        self.assertContains(response, 'id="my-product-delete-dialog"')

    def test_available_sold_and_unknown_filters(self):
        for status, titles in [('available', [self.available.title]), ('sold', [self.sold.title]), ('unknown', [self.available.title, self.sold.title])]:
            with self.subTest(status=status):
                response = self.client.get(self.url, {'status': status})
                self.assertCountEqual([product.title for product in response.context['page_obj']], titles)
                self.assertEqual(response.context['listing_totals']['total'], 2)

    def test_normal_user_without_products_gets_sell_empty_state(self):
        user = User.objects.create_user('new-listings-owner')
        self.client.force_login(user)
        response = self.client.get(self.url)
        self.assertFalse(user.is_staff)
        self.assertContains(response, 'Your first listing starts here')
        self.assertContains(response, reverse('products:sell'))
        self.assertNotContains(response, self.available.title)

    def test_empty_filter_can_return_to_all_products(self):
        self.available.status = 'sold'
        self.available.save()
        response = self.client.get(self.url, {'status': 'available'})
        self.assertContains(response, 'No available listings yet')
        self.assertContains(response, 'View All Listings')
        self.assertEqual(response.context['listing_totals']['total'], 2)

    def test_pagination_and_bad_page_numbers(self):
        from products.models import Product
        Product.objects.bulk_create([Product(seller=self.user, title=f'Extra {index}', slug=f'my-products-extra-{index}', price=10000) for index in range(13)])
        first = self.client.get(self.url)
        self.assertEqual(len(first.context['page_obj']), 12)
        self.assertTrue(first.context['page_obj'].has_next())
        second = self.client.get(self.url, {'page': 2})
        self.assertEqual(len(second.context['page_obj']), 3)
        invalid = self.client.get(self.url, {'page': 'invalid'})
        self.assertEqual(invalid.context['page_obj'].number, 1)
        overflow = self.client.get(self.url, {'page': 999})
        self.assertEqual(overflow.context['page_obj'].number, 2)

    def test_profile_activity_and_sidebar_link_to_my_products(self):
        response = self.client.get(reverse('profile'))
        self.assertContains(response, self.url)
        self.assertEqual(response.context['listing_count'], 2)
        self.assertContains(self.client.get(reverse('account_settings')), self.url)

    def test_owner_can_edit_using_existing_product_view(self):
        response = self.client.get(reverse('products:edit', args=[self.available.slug]))
        self.assertEqual(response.status_code, 200)
        response = self.client.post(reverse('products:edit', args=[self.available.slug]), {'title': 'Updated From My Products', 'price': 150000, 'category': self.category.pk, 'condition': 'good'})
        self.assertEqual(response.status_code, 302)
        self.available.refresh_from_db()
        self.assertEqual(self.available.title, 'Updated From My Products')
        self.assertEqual(self.available.seller_id, self.user.pk)

    def test_cannot_edit_or_delete_another_sellers_product(self):
        for action in ['edit', 'delete']:
            response = self.client.post(reverse('products:' + action, args=[self.foreign.slug]), {'seller': self.user.pk, 'next': self.url})
            self.assertEqual(response.status_code, 404)
        self.assertTrue(type(self.foreign).objects.filter(pk=self.foreign.pk).exists())

    def test_delete_returns_to_my_products_and_preserves_other_listings(self):
        response = self.client.post(reverse('products:delete', args=[self.available.slug]), {'next': self.url + '?status=available'})
        self.assertRedirects(response, self.url + '?status=available')
        self.assertFalse(type(self.available).objects.filter(pk=self.available.pk).exists())
        self.assertTrue(type(self.foreign).objects.filter(pk=self.foreign.pk).exists())
        self.assertTrue(type(self.sold).objects.filter(pk=self.sold.pk).exists())

    def test_delete_rejects_external_next_and_requires_csrf(self):
        url = reverse('products:delete', args=[self.available.slug])
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.user)
        self.assertEqual(strict.post(url, {'next': self.url}).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 405)
        response = self.client.post(url, {'next': 'https://untrusted.example/'})
        self.assertRedirects(response, reverse('products:home'))

    def test_uploaded_media_image_is_used_and_title_is_escaped(self):
        self.available.title = '<script>alert(1)</script>'
        self.available.save()
        photo = self.available.images.create(image='products/my-products-test.jpg', is_primary=True)
        response = self.client.get(self.url)
        self.assertContains(response, photo.image.url)
        self.assertNotContains(response, '/static/media/products/')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, self.available.title)


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class UniqueAccountEmailTests(TestCase):
    def data(self, **changes):
        return {'full_name': 'New Buyer', 'email': 'buyer@example.test',
                'password1': PASSWORD, 'password2': PASSWORD, **changes}

    def test_two_prevalidated_registrations_cannot_save_the_same_email(self):
        first = RegisterForm(self.data())
        second = RegisterForm(self.data(full_name='Other Buyer', email='BUYER@example.test'))
        self.assertTrue(first.is_valid(), first.errors)
        self.assertTrue(second.is_valid(), second.errors)
        first.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            second.save()
        self.assertEqual(User.objects.filter(email__iexact='buyer@example.test').count(), 1)

    def test_database_covers_direct_creates_and_email_updates(self):
        User.objects.create_user('one', 'one@example.test')
        for email in ('ONE@example.test', ' one@example.test '):
            with self.subTest(email=email), self.assertRaises(IntegrityError), transaction.atomic():
                User.objects.create_user('two', email)
        other = User.objects.create_user('other', 'other@example.test')
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=other.pk).update(email='ONE@example.test')
        User.objects.create_user('without-email-1')
        User.objects.create_user('without-email-2')

    def test_registration_race_returns_form_error_instead_of_server_error(self):
        original = RegisterForm.is_valid
        def competing_registration(form):
            valid = original(form)
            User.objects.create_user('winner', 'buyer@example.test')
            return valid
        with patch.object(RegisterForm, 'is_valid', competing_registration):
            response = self.client.post(reverse('register'), self.data())
        self.assertContains(response, 'already exists')
        self.assertEqual(User.objects.count(), 1)
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertFalse(Profile.objects.exists())

    def test_email_audit_does_not_change_data(self):
        User.objects.create_user('one', 'one@example.test')
        output = StringIO()
        call_command('audit_account_emails', stdout=output)
        self.assertIn('0 duplicate email group(s)', output.getvalue())
        self.assertNotIn('one@example.test', output.getvalue())
        self.assertEqual(User.objects.count(), 1)

    def test_google_signup_race_does_not_create_or_link_a_duplicate(self):
        from allauth.core.exceptions import ImmediateHttpResponse
        from allauth.socialaccount.models import SocialAccount, SocialLogin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from .adapters import SocialAccountAdapter
        existing = User.objects.create_user('existing', 'buyer@example.test')
        request = RequestFactory().get('/accounts/google/login/callback/')
        request.session = {}
        request._messages = FallbackStorage(request)
        login = SocialLogin(user=User(username='google-buyer', email='BUYER@example.test'),
                            account=SocialAccount(provider='google', uid='test-google-id'))
        with self.assertRaises(ImmediateHttpResponse) as error:
            SocialAccountAdapter(request).save_user(request, login)
        self.assertEqual(error.exception.response.url, reverse('login'))
        self.assertEqual(User.objects.count(), 1)
        self.assertFalse(SocialAccount.objects.filter(user=existing).exists())
