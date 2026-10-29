from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import AccountOrder
from products.models import Product
from .models import Review
from .forms import ReviewForm


class VerifiedPurchaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.buyer = User.objects.create_user(username="verified_buyer")
        cls.other = User.objects.create_user(username="different_buyer")
        cls.seller = User.objects.create_user(username="verified_seller")
        cls.other_seller = User.objects.create_user(username="different_seller")
        cls.product = Product.objects.create(seller=cls.seller, title="Coat", slug="verified-coat", price=100000)
        cls.other_product = Product.objects.create(seller=cls.other_seller, title="Coat", slug="other-coat", price=100000)

    def order(self, **overrides):
        data = dict(user=self.buyer, seller=self.seller, product=self.product,
                    number=f"V-{AccountOrder.objects.count()}", date=date.today(),
                    status=AccountOrder.Status.COMPLETED, title="Coat", subtotal=100000,
                    recipient="Buyer", address="Depok")
        data.update(overrides)
        return AccountOrder.objects.create(**data)

    def url(self, seller=None):
        return reverse("reviews:create_review", args=[(seller or self.seller).pk])

    def submit(self, order, **extra):
        self.client.force_login(self.buyer)
        return self.client.post(self.url(), {"order": order.pk, "rating": 5,
                                "title": "Great seller", "comment": "Helpful communication.", **extra})

    def test_completed_purchase_can_be_reviewed_and_badge_is_shown(self):
        order = self.order()
        response = self.submit(order)
        self.assertRedirects(response, reverse("reviews:seller_reviews", args=[self.seller.pk]))
        review = Review.objects.get(order=order)
        self.assertEqual(review.reviewer, self.buyer)
        self.assertEqual(review.seller, self.seller)
        self.assertTrue(review.is_verified_purchase)
        self.assertContains(self.client.get(response.url), "Verified buyer")

    def test_without_purchase_cannot_create_review(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(self.url()).status_code, 403)
        self.assertEqual(self.client.post(self.url(), {"rating": 5, "title": "Fake", "comment": "Fake"}).status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_pending_and_in_transit_orders_are_not_eligible(self):
        for status in [AccountOrder.Status.AWAITING_PAYMENT, AccountOrder.Status.IN_TRANSIT]:
            order = self.order(status=status)
            self.assertEqual(self.submit(order).status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_another_buyers_order_is_rejected(self):
        order = self.order(user=self.other)
        self.assertEqual(self.submit(order).status_code, 403)
        self.assertFalse(Review.objects.exists())

    def test_another_sellers_order_cannot_be_used(self):
        valid = self.order()
        wrong = self.order(seller=self.other_seller, product=self.other_product)
        response = self.submit(wrong)
        self.assertContains(response, "Select a valid choice", status_code=200)
        self.assertFalse(Review.objects.exists())

    def test_posted_reviewer_and_seller_are_ignored(self):
        order = self.order()
        self.submit(order, reviewer=self.other.pk, seller=self.other_seller.pk)
        review = Review.objects.get(order=order)
        self.assertEqual((review.reviewer_id, review.seller_id), (self.buyer.pk, self.seller.pk))

    def test_same_order_cannot_create_second_review(self):
        order = self.order()
        self.submit(order)
        self.assertEqual(self.submit(order).status_code, 403)
        self.assertEqual(Review.objects.count(), 1)

    def test_unique_order_constraint(self):
        order = self.order()
        Review.objects.create(order=order, reviewer=self.buyer, seller=self.seller, rating=5, title="First", comment="First")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(order=order, reviewer=self.buyer, seller=self.seller, rating=4, title="Duplicate", comment="Duplicate")

    def test_different_completed_orders_allow_separate_reviews(self):
        first, second = self.order(), self.order()
        self.submit(first)
        self.submit(second)
        self.assertEqual(Review.objects.count(), 2)

    def test_legacy_review_stays_visible_without_verified_badge(self):
        old = Review.objects.create(reviewer=self.buyer, seller=self.seller, rating=4, title="Old review", comment="Preserved")
        self.assertFalse(old.is_verified_purchase)
        response = self.client.get(reverse("reviews:seller_reviews", args=[self.seller.pk]))
        self.assertContains(response, "Old review")
        self.assertNotContains(response, "Verified buyer")

    def test_legacy_order_is_not_matched_by_title(self):
        order = self.order(product=None, seller=None)
        self.assertEqual(self.submit(order).status_code, 403)
        order.refresh_from_db()
        self.assertIsNone(order.seller_id)

    def test_badge_checks_buyer_seller_and_completed_status(self):
        for values in [{"user": self.other}, {"seller": self.other_seller}, {"status": AccountOrder.Status.AWAITING_PAYMENT}]:
            review = Review(reviewer=self.buyer, seller=self.seller, order=self.order(**values), rating=4)
            self.assertFalse(review.is_verified_purchase)

    def test_order_specific_form_uses_only_its_order(self):
        order, second = self.order(), self.order()
        url = reverse("reviews:create_order_review", args=[order.pk])
        self.client.force_login(self.buyer)
        response = self.client.get(url)
        self.assertEqual(list(response.context["form"].fields["order"].queryset), [order])
        response = self.client.post(url, {"order": second.pk, "rating": 5, "title": "Fake", "comment": "Fake"})
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Review.objects.exists())

    def test_order_specific_url_rejects_other_buyer(self):
        order = self.order(user=self.other)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse("reviews:create_order_review", args=[order.pk])).status_code, 404)

    def test_reviewed_order_link_opens_edit(self):
        order = self.order()
        self.submit(order)
        review = Review.objects.get(order=order)
        self.assertRedirects(self.client.get(reverse("reviews:create_order_review", args=[order.pk])),
                             reverse("reviews:edit_review", args=[review.pk]))

    def test_order_detail_shows_create_then_edit_link(self):
        order = self.order()
        self.client.force_login(self.buyer)
        url = reverse("order_detail", args=[order.pk])
        self.assertContains(self.client.get(url), reverse("reviews:create_order_review", args=[order.pk]))
        self.submit(order)
        review = Review.objects.get(order=order)
        self.assertContains(self.client.get(url), reverse("reviews:edit_review", args=[review.pk]))

    def test_pending_order_detail_does_not_offer_review(self):
        order = self.order(status=AccountOrder.Status.AWAITING_PAYMENT)
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("order_detail", args=[order.pk]))
        self.assertNotContains(response, reverse("reviews:create_order_review", args=[order.pk]))

    def test_checkout_records_product_and_seller_without_completing_payment(self):
        self.client.force_login(self.buyer)
        session = self.client.session
        session["bag"] = {str(self.product.pk): 1, str(self.other_product.pk): 1}
        session["transaction_address"] = dict(recipient="Buyer", phone="0812", address="Street", city="Depok", postal_code="16424", country="Indonesia")
        session["transaction_payment"] = "bank_transfer"
        session.save()
        response = self.client.post(reverse("transaction:confirmation"))
        self.assertEqual(response.status_code, 302)
        orders = list(AccountOrder.objects.filter(user=self.buyer))
        self.assertEqual(len(orders), 2)
        self.assertEqual({(o.product_id, o.seller_id) for o in orders},
                         {(self.product.pk, self.seller.pk), (self.other_product.pk, self.other_seller.pk)})
        self.assertTrue(all(o.status == AccountOrder.Status.AWAITING_PAYMENT for o in orders))
        self.client.get(reverse("transaction:confirmation"))
        self.assertEqual(AccountOrder.objects.count(), 2)

    def test_order_deletion_preserves_old_review_without_badge(self):
        order = self.order()
        self.submit(order)
        review = Review.objects.get(order=order)
        order.delete()
        review.refresh_from_db()
        self.assertIsNone(review.order_id)
        self.assertFalse(review.is_verified_purchase)

    def seller_page(self, **query):
        return self.client.get(reverse('reviews:seller_reviews', args=[self.seller.pk]), query)

    def test_order_removed_between_validation_and_save_is_handled(self):
        order = self.order()
        original_valid = ReviewForm.is_valid

        def remove_order(form):
            valid = original_valid(form)
            if valid:
                AccountOrder.objects.filter(pk=order.pk).delete()
            return valid

        with patch.object(ReviewForm, 'is_valid', remove_order):
            response = self.submit(order)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer eligible')
        self.assertFalse(Review.objects.exists())

    def test_edit_cannot_change_purchase_or_identity(self):
        order = self.order()
        self.submit(order)
        review = Review.objects.get(order=order)
        other_order = self.order(user=self.other, seller=self.other_seller, product=self.other_product)
        self.client.post(reverse('reviews:edit_review', args=[review.pk]), {
            'rating': 3, 'title': 'Updated', 'comment': 'Updated',
            'order': other_order.pk, 'reviewer': self.other.pk, 'seller': self.other_seller.pk,
        })
        review.refresh_from_db()
        self.assertEqual((review.order_id, review.reviewer_id, review.seller_id),
                         (order.pk, self.buyer.pk, self.seller.pk))
        self.assertEqual(review.rating, 3)

    def test_available_purchase_offers_rate_seller(self):
        self.order()
        self.client.force_login(self.buyer)
        self.assertContains(self.seller_page(), 'Rate Seller')

    def test_all_purchases_reviewed_offers_edit_instead_of_rate(self):
        order = self.order()
        self.submit(order)
        review = Review.objects.get(order=order)
        response = self.seller_page()
        self.assertContains(response, 'Edit My Review')
        self.assertNotContains(response, 'Rate Seller')
        self.assertNotContains(response, 'Write a Seller Review')
        self.assertContains(response, reverse('reviews:edit_review', args=[review.pk]))

    def test_unqualified_buyer_is_guided_to_orders(self):
        self.order(status=AccountOrder.Status.AWAITING_PAYMENT)
        self.client.force_login(self.buyer)
        response = self.seller_page()
        self.assertContains(response, 'View My Orders')
        self.assertNotContains(response, 'Rate Seller')
        self.assertNotContains(response, 'Write a Seller Review')

    def test_second_unreviewed_purchase_still_offers_rate_seller(self):
        self.submit(self.order())
        self.order()
        response = self.seller_page()
        self.assertContains(response, 'Rate Seller')
        self.assertNotContains(response, 'Edit My Review')

    def test_guest_still_has_login_entry_to_rate_seller(self):
        self.assertContains(self.seller_page(), 'Rate Seller')

    def test_deleted_review_makes_its_purchase_available_again(self):
        order = self.order()
        self.submit(order)
        review = Review.objects.get(order=order)
        self.client.post(reverse('reviews:delete_review', args=[review.pk]))
        self.assertContains(self.seller_page(), 'Rate Seller')

    def test_ajax_filter_preserves_reviewed_purchase_action(self):
        self.submit(self.order())
        response = self.client.get(reverse('reviews:seller_reviews', args=[self.seller.pk]),
                                   {'rating': '1'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        html = response.json()['html']
        self.assertIn('Edit My Review', html)
        self.assertNotIn('Rate Seller', html)
