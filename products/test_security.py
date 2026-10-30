import json
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse

from .decorators import TOO_MANY_TEXT, owner_required, rate_limit
from .models import Product


def _request(method='post', user=None, ajax=False, **extra):
    factory = RequestFactory()
    headers = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'} if ajax else {}
    request = getattr(factory, method)('/products/thing/', **headers, **extra)
    SessionMiddleware(lambda r: HttpResponse()).process_request(request)
    request.user = user or AnonymousUser()
    return request


class OwnerRequiredTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('sec-owner')
        cls.other = get_user_model().objects.create_user('sec-other')
        cls.product = Product.objects.create(seller=cls.owner, title='Guarded Coat', price=100000)

    def test_owner_gets_the_listing_passed_in(self):
        seen = []
        view = owner_required()(lambda request, product: seen.append(product) or HttpResponse('ok'))
        request = _request('get', user=self.owner)
        self.assertEqual(view(request, slug=self.product.slug).content, b'ok')
        self.assertEqual(seen, [self.product])

    def test_other_users_and_guests_get_404(self):
        view = owner_required()(lambda request, product: HttpResponse('ok'))
        for user in [self.other, None]:
            with self.subTest(user=user), self.assertRaises(Http404):
                view(_request('get', user=user), slug=self.product.slug)

    def test_custom_queryset_is_used(self):
        view = owner_required(lambda: Product.objects.none())(lambda request, product: HttpResponse('ok'))
        with self.assertRaises(Http404):
            view(_request('get', user=self.owner), slug=self.product.slug)

    def test_edit_and_delete_views_refuse_other_sellers(self):
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('products:edit', args=[self.product.slug])).status_code, 404)
        self.assertEqual(self.client.post(reverse('products:delete', args=[self.product.slug])).status_code, 404)
        self.assertTrue(Product.objects.filter(pk=self.product.pk).exists())


class RateLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user('sec-limited')
        cls.seller = get_user_model().objects.create_user('sec-seller')
        cls.product = Product.objects.create(seller=cls.seller, title='Popular Bag', price=90000)

    def setUp(self):
        cache.clear()
        self.view = rate_limit('test-scope', limit=2, window=60)(lambda request: HttpResponse('ok'))

    def test_requests_over_the_limit_are_blocked_until_the_window_ends(self):
        request = _request(user=self.user)
        self.assertEqual(self.view(request).status_code, 200)
        self.assertEqual(self.view(request).status_code, 200)
        blocked = self.view(_request(user=self.user, ajax=True))
        self.assertEqual(blocked.status_code, 429)
        self.assertTrue(1 <= int(blocked['Retry-After']) <= 60)
        with mock.patch('products.decorators.time.time', return_value=10 ** 9 + 120):
            self.assertEqual(self.view(_request(user=self.user)).status_code, 200)

    def test_ajax_block_returns_a_toast_and_form_error(self):
        for _ in range(2):
            self.view(_request(user=self.user, ajax=True))
        data = json.loads(self.view(_request(user=self.user, ajax=True)).content)
        self.assertFalse(data['ok'])
        self.assertEqual(data['toast'], {'kind': 'error', 'text': TOO_MANY_TEXT})
        self.assertEqual(data['errors'], {'__all__': [TOO_MANY_TEXT]})

    def test_plain_form_block_redirects_back_with_a_toast(self):
        for _ in range(2):
            self.view(_request(user=self.user))
        request = _request(user=self.user, data={'next': '/products/picked/'})
        response = self.view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/products/picked/')
        self.assertEqual(request.session['bag_toast']['text'], TOO_MANY_TEXT)

    def test_unsafe_next_falls_back_to_home(self):
        for _ in range(2):
            self.view(_request(user=self.user))
        response = self.view(_request(user=self.user, data={'next': 'https://evil.example/'}))
        self.assertEqual(response.url, reverse('products:home'))

    def test_get_requests_are_not_counted(self):
        for _ in range(5):
            self.assertEqual(self.view(_request('get', user=self.user)).status_code, 200)
        self.assertEqual(self.view(_request(user=self.user)).status_code, 200)

    def test_each_user_and_guest_session_has_its_own_budget(self):
        other = get_user_model().objects.create_user('sec-limited-2')
        for _ in range(2):
            self.view(_request(user=self.user))
        self.assertEqual(self.view(_request(user=self.user)).status_code, 302)
        self.assertEqual(self.view(_request(user=other)).status_code, 200)
        self.assertEqual(self.view(_request()).status_code, 200)

    def test_counter_that_expired_between_add_and_incr_restarts_at_one(self):
        with mock.patch('products.decorators.cache.incr', side_effect=ValueError):
            self.assertEqual(self.view(_request(user=self.user)).status_code, 200)

    def test_wishlist_endpoint_is_limited_end_to_end(self):
        buyer = get_user_model().objects.create_user('sec-buyer')
        self.client.force_login(buyer)
        url = reverse('products:wish_add', args=[self.product.slug])
        ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        for _ in range(40):
            self.assertEqual(self.client.post(url, **ajax).status_code, 200)
        response = self.client.post(url, **ajax)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response)

    def test_bag_endpoint_is_limited_for_guests(self):
        url = reverse('products:bag_add', args=[self.product.slug])
        ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
        for _ in range(60):
            self.client.post(url, **ajax)
        self.assertEqual(self.client.post(url, **ajax).status_code, 429)
