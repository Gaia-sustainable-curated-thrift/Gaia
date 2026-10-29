"""User module unit and request tests; run with python manage.py test accounts.

Uses an isolated test database and in-memory emails; no live OAuth or SMTP.
"""

import re
from datetime import date
from io import StringIO
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

    def test_login_rejects_wrong_password_unknown_and_ambiguous_email(self):
        User.objects.create_user('duplicate', 'gaia@example.com', PASSWORD)
        for identifier, password in [('gaia', 'wrong'), ('missing@example.com', PASSWORD),
                                     ('gaia@example.com', PASSWORD)]:
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
