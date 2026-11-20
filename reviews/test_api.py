from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient, APITestCase

from accounts.models import AccountOrder
from products.models import Product
from .models import Review, ReviewReport
from .serializers import ReviewWriteSerializer


class ReviewAPITests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.buyer = User.objects.create_user(username='api-buyer', first_name='Private Buyer')
        cls.seller = User.objects.create_user(username='api-seller')
        cls.other = User.objects.create_user(username='api-other')
        cls.other_seller = User.objects.create_user(username='api-other-seller')
        cls.product = Product.objects.create(
            seller=cls.seller, title='Coat', slug='api-coat', price=100000,
        )
        Product.objects.create(seller=cls.other_seller, title='Hat', slug='api-hat', price=50000)

    def setUp(self):
        self.order = self.make_order()

    def make_order(self, **overrides):
        data = {
            'user': self.buyer, 'seller': self.seller, 'product': self.product,
            'number': f'API-{AccountOrder.objects.count()}', 'date': date.today(),
            'status': AccountOrder.Status.COMPLETED, 'title': 'Coat',
            'subtotal': 100000, 'recipient': 'Buyer', 'address': 'Depok',
        }
        data.update(overrides)
        return AccountOrder.objects.create(**data)

    def url(self, name='review-list', *args):
        return reverse(f'reviews_api:{name}', args=args)

    def payload(self, **overrides):
        return {
            'order': self.order.pk, 'rating': 5, 'title': 'Seller ramah',
            'comment': 'Komunikasi cepat.', **overrides,
        }

    def login(self, user=None):
        # Exercise real Django sessions rather than bypassing authentication.
        self.client.force_login(user or self.buyer)

    def create(self, **overrides):
        return self.client.post(self.url(), self.payload(**overrides), format='json')

    def review(self, **overrides):
        return Review.objects.create(
            **{'order': self.order, 'reviewer': self.buyer, 'seller': self.seller,
               'rating': 4, 'title': 'Existing', 'comment': 'Existing comment.', **overrides},
        )

    def test_completed_order_creates_review_with_authenticated_identity(self):
        self.login()
        response = self.create(is_friendly=True, is_anonymous=True)
        self.assertEqual(response.status_code, 201)
        review = Review.objects.get()
        self.assertEqual((review.reviewer_id, review.seller_id, review.order_id),
                         (self.buyer.pk, self.seller.pk, self.order.pk))
        self.assertTrue(review.is_friendly)
        self.assertTrue(review.is_anonymous)
        self.assertEqual(response.data['id'], review.pk)
        self.assertEqual(response.data['helpful_count'], 0)
        self.assertTrue(response.data['is_owner'])
        self.assertTrue(response.data['is_verified_purchase'])
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response['Cache-Control'], 'private, no-store')

    def test_every_rating_from_one_to_five_is_accepted(self):
        self.login()
        for rating in range(1, 6):
            with self.subTest(rating=rating):
                order = self.make_order()
                self.assertEqual(self.create(order=order.pk, rating=rating).status_code, 201)

    def test_invalid_ratings_are_rejected(self):
        self.login()
        for rating in [0, 6, -1, 3.5, 'bad', None, True]:
            with self.subTest(rating=rating):
                response = self.create(rating=rating)
                self.assertEqual(response.status_code, 400)
                self.assertIn('rating', response.data)
        self.assertFalse(Review.objects.exists())

    def test_required_blank_and_oversized_fields_are_rejected(self):
        self.login()
        for field in ['order', 'rating', 'title', 'comment']:
            data = self.payload()
            data.pop(field)
            self.assertEqual(self.client.post(self.url(), data, format='json').status_code, 400)
        for values in [
            {'title': ''}, {'comment': '  '}, {'title': 'a' * 101},
            {'comment': 'a' * 2001}, {'order': 0}, {'order': None},
        ]:
            with self.subTest(values=values):
                self.assertEqual(self.create(**values).status_code, 400)
        self.assertFalse(Review.objects.exists())

    def test_identity_and_server_fields_cannot_be_submitted(self):
        self.login()
        for field, value in [
            ('reviewer', self.other.pk), ('seller', self.other_seller.pk),
            ('seller_reply', 'Fake reply'), ('helpful_by', [self.other.pk]),
            ('created_at', '2020-01-01'), ('is_verified_purchase', True),
        ]:
            with self.subTest(field=field):
                response = self.create(**{field: value})
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)
        self.assertFalse(Review.objects.exists())

    def test_guest_cannot_use_any_write_or_private_collection(self):
        review = self.review()
        cases = [
            ('post', self.url(), self.payload()),
            ('patch', self.url('review-detail', review.pk), {'rating': 3}),
            ('put', self.url('review-detail', review.pk), {}),
            ('delete', self.url('review-detail', review.pk), {}),
            ('post', self.url('review-helpful', review.pk), {}),
            ('post', self.url('review-reply', review.pk), {'reply': 'Thanks'}),
            ('delete', self.url('review-reply', review.pk), {}),
            ('post', self.url('review-report', review.pk), {'reason': 'spam'}),
        ]
        for method, url, data in cases:
            with self.subTest(method=method, url=url):
                response = getattr(self.client, method)(url, data, format='json')
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response['Content-Type'], 'application/json')
        for url in [self.url('review-mine'), self.url('eligible-orders', self.seller.pk)]:
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(Review.objects.count(), 1)
        self.assertFalse(ReviewReport.objects.exists())

    def test_ineligible_orders_are_rejected_without_disclosing_owner(self):
        self.login()
        inactive = get_user_model().objects.create_user(username='inactive', is_active=False)
        orders = [
            self.make_order(user=self.other),
            self.make_order(status=AccountOrder.Status.AWAITING_PAYMENT),
            self.make_order(status=AccountOrder.Status.IN_TRANSIT),
            self.make_order(seller=None), self.make_order(seller=self.buyer),
            self.make_order(seller=inactive),
        ]
        errors = []
        for order_id in [order.pk for order in orders] + [999999]:
            with self.subTest(order_id=order_id):
                response = self.create(order=order_id)
                self.assertEqual(response.status_code, 400)
                errors.append(response.data)
        self.assertTrue(all(error == errors[0] for error in errors))
        self.assertFalse(Review.objects.exists())

    def test_order_seller_is_derived_and_separate_purchases_are_allowed(self):
        self.login()
        other_order = self.make_order(seller=self.other_seller, product=self.other_seller.products.first())
        response = self.create(order=other_order.pk)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['seller'], self.other_seller.pk)
        self.assertEqual(self.create().status_code, 201)
        self.assertEqual(self.create().status_code, 400)
        self.assertEqual(Review.objects.count(), 2)

    def test_order_eligibility_is_rechecked_after_validation(self):
        self.login()
        original = ReviewWriteSerializer.is_valid

        def change_order(serializer, *args, **kwargs):
            valid = original(serializer, *args, **kwargs)
            AccountOrder.objects.filter(pk=self.order.pk).update(status=AccountOrder.Status.IN_TRANSIT)
            return valid

        with patch.object(ReviewWriteSerializer, 'is_valid', change_order):
            self.assertEqual(self.create().status_code, 400)
        self.assertFalse(Review.objects.exists())

    def test_duplicate_race_becomes_validation_error(self):
        self.login()
        with patch('reviews.serializers.Review.objects.create', side_effect=IntegrityError('duplicate')):
            self.assertEqual(self.create().status_code, 400)
        self.assertFalse(Review.objects.exists())

    def test_author_can_patch_put_and_delete_without_changing_identity(self):
        review = self.review()
        self.login()
        url = self.url('review-detail', review.pk)
        self.assertEqual(self.client.patch(url, {'rating': 2}, format='json').status_code, 200)
        response = self.client.put(url, {'rating': 3, 'title': 'Updated', 'comment': 'Updated'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['rating'], 3)
        for field, value in [('order', self.make_order().pk), ('seller', self.other_seller.pk),
                             ('reviewer', self.other.pk), ('seller_reply', 'Forged')]:
            self.assertEqual(self.client.patch(url, {field: value}, format='json').status_code, 400)
        review.refresh_from_db()
        self.assertEqual((review.order_id, review.reviewer_id, review.seller_id),
                         (self.order.pk, self.buyer.pk, self.seller.pk))
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertTrue(AccountOrder.objects.filter(pk=self.order.pk).exists())
        self.assertEqual(self.create().status_code, 201)

    def test_other_users_including_seller_cannot_edit_or_delete(self):
        review = self.review()
        url = self.url('review-detail', review.pk)
        for user in [self.other, self.seller]:
            self.login(user)
            self.assertEqual(self.client.patch(url, {'rating': 1}, format='json').status_code, 403)
            self.assertEqual(self.client.put(url, {'rating': 1, 'title': 'X', 'comment': 'X'}, format='json').status_code, 403)
            self.assertEqual(self.client.delete(url).status_code, 403)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)

    def test_invalid_patch_preserves_review(self):
        review = self.review()
        self.login()
        self.assertEqual(self.client.patch(self.url('review-detail', review.pk),
                                          {'rating': 8}, format='json').status_code, 400)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)

    def test_read_privacy_matches_website_for_guest_and_logged_in_user(self):
        review = self.review()
        url = self.url('review-detail', review.pk)
        response = self.client.get(url)
        self.assertIsNone(response.data['reviewer'])
        self.assertIsNone(response.data['order'])
        self.assertEqual(response.data['reviewer_name'], 'GAIA member')
        self.login(self.other)
        response = self.client.get(url)
        self.assertEqual(response.data['reviewer'], self.buyer.pk)
        self.assertEqual(response.data['reviewer_name'], 'Private Buyer')
        self.assertIsNone(response.data['order'])
        review.is_anonymous = True
        review.save()
        for user in [self.other, self.seller, self.buyer]:
            self.login(user)
            response = self.client.get(url)
            self.assertIsNone(response.data['reviewer'])
            self.assertEqual(response.data['reviewer_name'], 'Anonymous')
            self.assertNotIn('Private Buyer', response.content.decode())
        self.assertEqual(response.data['order'], self.order.pk)

    def test_list_filter_sort_pagination_and_summary(self):
        first = self.review(rating=2)
        second = self.review(order=self.make_order(), rating=5, title='Second')
        first.helpful_by.add(self.other)
        url = self.url('review-seller-reviews', self.seller.pk)
        response = self.client.get(url, {'rating': 2})
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], first.pk)
        response = self.client.get(url, {'sort': 'rating', 'page_size': 1})
        self.assertEqual(response.data['results'][0]['id'], second.pk)
        self.assertIsNotNone(response.data['next'])
        response = self.client.get(url, {'sort': 'helpful'})
        self.assertEqual(response.data['results'][0]['id'], first.pk)
        response = self.client.get(self.url(), {'seller': self.seller.pk})
        self.assertEqual(response.data['count'], 2)
        summary = self.client.get(self.url('seller-summary', self.seller.pk), {'rating': 5}).data
        self.assertEqual(summary['total_reviews'], 2)
        self.assertEqual(summary['average_rating'], 3.5)
        self.assertEqual(sum(row['count'] for row in summary['rating_breakdown']), 2)

    def test_invalid_filters_and_pages_return_json_errors(self):
        self.review()
        for params in [{'rating': 0}, {'rating': 'bad'}, {'sort': 'bad'}, {'seller': 'bad'}]:
            self.assertEqual(self.client.get(self.url(), params).status_code, 400)
        response = self.client.get(self.url(), {'page': 999})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_mine_returns_only_authenticated_users_reviews(self):
        own = self.review()
        self.review(order=self.make_order(user=self.other), reviewer=self.other)
        self.login()
        response = self.client.get(self.url('review-mine'))
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], own.pk)

    def test_eligible_orders_only_include_own_unreviewed_completed_purchases(self):
        self.review()
        eligible = self.make_order()
        self.make_order(user=self.other)
        self.make_order(status=AccountOrder.Status.IN_TRANSIT)
        self.make_order(seller=self.other_seller)
        self.login()
        response = self.client.get(self.url('eligible-orders', self.seller.pk))
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], eligible.pk)
        self.assertNotIn('address', response.data['results'][0])
        self.login(self.seller)
        self.assertEqual(self.client.get(self.url('eligible-orders', self.seller.pk)).data['count'], 0)

    def test_summary_empty_seller_and_missing_sellers(self):
        summary = self.client.get(self.url('seller-summary', self.other_seller.pk)).data
        self.assertEqual(summary['total_reviews'], 0)
        self.assertIsNone(summary['average_rating'])
        for seller_id in [999999, self.other.pk]:
            for name in ['seller-summary', 'review-seller-reviews']:
                response = self.client.get(self.url(name, seller_id))
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response['Content-Type'], 'application/json')
        get_user_model().objects.filter(pk=self.seller.pk).update(is_active=False)
        self.assertEqual(self.client.get(self.url('seller-summary', self.seller.pk)).status_code, 404)

    def test_helpful_toggle_and_owner_restrictions(self):
        review = self.review()
        url = self.url('review-helpful', review.pk)
        for user in [self.buyer, self.seller]:
            self.login(user)
            self.assertEqual(self.client.post(url).status_code, 403)
        self.login(self.other)
        self.assertEqual(self.client.post(url).data, {'has_voted': True, 'helpful_count': 1})
        detail = self.client.get(self.url('review-detail', review.pk)).data
        self.assertTrue(detail['has_voted'])
        self.assertEqual(self.client.post(url).data, {'has_voted': False, 'helpful_count': 0})
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_only_seller_can_create_update_and_remove_reply(self):
        review = self.review()
        url = self.url('review-reply', review.pk)
        for user in [self.buyer, self.other]:
            self.login(user)
            self.assertEqual(self.client.post(url, {'reply': 'No'}, format='json').status_code, 403)
            self.assertEqual(self.client.delete(url).status_code, 403)
        self.login(self.seller)
        for reply in ['', ' ', 'a' * 1001]:
            self.assertEqual(self.client.post(url, {'reply': reply}, format='json').status_code, 400)
        for reply in ['Thank you!', 'Updated reply']:
            response = self.client.post(url, {'reply': reply}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['seller_reply'], reply)
            self.assertIsNotNone(response.data['seller_replied_at'])
        response = self.client.delete(url)
        self.assertEqual(response.data['seller_reply'], '')
        self.assertIsNone(response.data['seller_replied_at'])

    def test_reports_are_validated_idempotent_and_private(self):
        review = self.review()
        url = self.url('review-report', review.pk)
        self.login()
        self.assertEqual(self.client.post(url, {'reason': 'spam'}, format='json').status_code, 403)
        self.login(self.other)
        for data in [{}, {'reason': 'invalid'}, {'reason': 'spam', 'details': 'a' * 1001}]:
            self.assertEqual(self.client.post(url, data, format='json').status_code, 400)
        response = self.client.post(url, {'reason': 'privacy', 'details': 'Private report'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.client.post(url, {'reason': 'spam'}, format='json').status_code, 200)
        self.assertEqual(ReviewReport.objects.count(), 1)
        self.assertEqual(ReviewReport.objects.get().reason, 'privacy')
        response = self.client.get(self.url('review-detail', review.pk))
        self.assertTrue(response.data['has_reported'])
        self.assertNotIn('Private report', response.content.decode())
        self.client.logout()
        self.assertFalse(self.client.get(self.url('review-detail', review.pk)).data['has_reported'])

    def test_deleted_order_keeps_legacy_review_readable_and_editable(self):
        review = self.review()
        self.order.delete()
        self.login()
        url = self.url('review-detail', review.pk)
        response = self.client.get(url)
        self.assertIsNone(response.data['order'])
        self.assertFalse(response.data['is_verified_purchase'])
        self.assertEqual(self.client.patch(url, {'rating': 3}, format='json').status_code, 200)

    def test_malformed_json_and_non_object_payload_are_validation_errors(self):
        self.login()
        self.assertEqual(self.client.post(self.url(), '{', content_type='application/json').status_code, 400)
        for data in [[], ['rating'], 42, 'text']:
            self.assertEqual(self.client.post(self.url(), data, format='json').status_code, 400)

    @override_settings(DEBUG=False)
    def test_missing_review_and_wrong_methods_return_json(self):
        response = self.client.get(self.url('review-detail', 999999))
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response['Content-Type'], 'application/json')
        self.login()
        response = self.client.delete(self.url())
        self.assertEqual(response.status_code, 405)
        self.assertEqual(response['Content-Type'], 'application/json')

    def test_session_authentication_requires_csrf_for_writes(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        self.assertEqual(client.post(self.url(), self.payload(), format='json').status_code, 403)
        csrf_response = client.get(self.url('csrf'))
        self.assertEqual(csrf_response.status_code, 200)
        self.assertIn('csrftoken', client.cookies)
        response = client.post(self.url(), self.payload(), format='json',
                               HTTP_X_CSRFTOKEN=csrf_response.data['csrfToken'])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Review.objects.get().reviewer_id, self.buyer.pk)

    def test_existing_html_routes_still_resolve_and_render(self):
        self.review()
        response = self.client.get(reverse('reviews:seller_reviews', args=[self.seller.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/html', response['Content-Type'])
        self.assertContains(response, 'Existing comment.')

    def test_existing_login_form_session_can_create_review_with_csrf(self):
        password = 'Review-api-test-2026!'
        self.buyer.set_password(password)
        self.buyer.save(update_fields=['password'])
        client = APIClient(enforce_csrf_checks=True)
        token = client.get(self.url('csrf')).data['csrfToken']
        response = client.post(reverse('login'), {
            'username': self.buyer.username, 'password': password,
            'csrfmiddlewaretoken': token,
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('sessionid', client.cookies)
        # Django rotates CSRF on login; fetch the new token with the same cookies.
        token = client.get(self.url('csrf')).data['csrfToken']
        response = client.post(self.url(), self.payload(), format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Review.objects.get().reviewer_id, self.buyer.pk)
