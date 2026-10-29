from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from products.models import Product
from django.template import Context, Template

from .forms import ReviewForm
from .models import Review, ReviewReport


class ReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.seller = User.objects.create_user(username="test_seller")
        cls.buyer = User.objects.create_user(username="review_author_keisha", first_name="Keisha")
        cls.other = User.objects.create_user(username="other_user", first_name="Salma")
        cls.empty_seller = User.objects.create_user(username="empty_seller")
        for seller in [cls.seller, cls.empty_seller]:
            Product.objects.create(seller=seller, title="Vintage coat", slug=f"coat-{seller.pk}", price=100000)
        cls.review = Review.objects.create(
            reviewer=cls.buyer, seller=cls.seller, rating=4,
            title="Seller ramah", comment="Barang sesuai deskripsi.",
        )

    def url(self, name, obj=None):
        obj = obj or (self.seller if name in ["create_review", "seller_reviews"] else self.review)
        return reverse(f"reviews:{name}", args=[obj.pk])

    def data(self, **extra):
        return {"rating": 5, "title": "Seller helpful", "comment": "Responsnya cepat.", **extra}

    def login(self, user=None):
        self.client.force_login(user or self.buyer)

    def test_guest_can_read_reviews(self):
        response = self.client.get(self.url("seller_reviews"))
        self.assertContains(response, self.review.title)
        self.assertEqual(response.context["total_reviews"], 1)

    def test_reviewer_identity_requires_login(self):
        response = self.client.get(self.url("seller_reviews"))
        self.assertNotContains(response, "Keisha")
        self.assertContains(response, "GAIA member")
        self.login(self.other)
        self.assertContains(self.client.get(self.url("seller_reviews")), "Keisha")

    def test_anonymous_identity_hidden_in_html_and_ajax(self):
        self.review.is_anonymous = True
        self.review.save()
        self.login(self.other)
        response = self.client.get(self.url("seller_reviews"))
        self.assertContains(response, "Anonymous")
        self.assertNotContains(response, "Keisha")
        response = self.client.get(self.url("seller_reviews"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertNotIn("Keisha", response.json()["html"])

    def test_empty_seller_summary(self):
        response = self.client.get(self.url("seller_reviews", self.empty_seller))
        self.assertIsNone(response.context["average_rating"])
        self.assertEqual(response.context["total_reviews"], 0)
        self.assertContains(response, "No reviews yet")

    def test_unknown_non_seller_or_inactive_seller_returns_404(self):
        self.empty_seller.is_active = False
        self.empty_seller.save()
        for pk in [999999, self.other.pk, self.empty_seller.pk]:
            self.assertEqual(self.client.get(reverse("reviews:seller_reviews", args=[pk])).status_code, 404)

    def test_filters_leave_overall_summary_unchanged(self):
        Review.objects.create(reviewer=self.other, seller=self.seller, rating=2, title="Slow", comment="Slow reply.")
        response = self.client.get(self.url("seller_reviews"), {"rating": "4"})
        self.assertEqual(response.context["average_rating"], 3)
        self.assertEqual(response.context["total_reviews"], 2)
        self.assertEqual(response.context["filtered_count"], 1)
        self.assertEqual([r.pk for r in response.context["reviews"]], [self.review.pk])
        self.assertEqual(sum(row["count"] for row in response.context["rating_breakdown"]), 2)

    def test_invalid_filters_and_sort_fall_back(self):
        for rating in ["abc", "6", "-1", ""]:
            response = self.client.get(self.url("seller_reviews"), {"rating": rating, "sort": "invalid"})
            self.assertEqual(response.context["filtered_count"], 1)
            self.assertEqual(response.context["selected_rating"], "")
            self.assertEqual(response.context["selected_sort"], "newest")

    def test_filter_empty_state(self):
        response = self.client.get(self.url("seller_reviews"), {"rating": "1"})
        self.assertContains(response, "No matching reviews")
        self.assertEqual(response.context["filtered_count"], 0)

    def test_sort_rating_and_helpful(self):
        other = Review.objects.create(reviewer=self.other, seller=self.seller, rating=5, title="Great", comment="Great seller.")
        self.review.helpful_by.add(self.empty_seller)
        response = self.client.get(self.url("seller_reviews"), {"sort": "rating"})
        self.assertEqual(response.context["reviews"][0].pk, other.pk)
        response = self.client.get(self.url("seller_reviews"), {"sort": "helpful"})
        self.assertEqual(response.context["reviews"][0].pk, self.review.pk)

    def test_pagination_and_bad_page(self):
        Review.objects.bulk_create([
            Review(reviewer=self.buyer, seller=self.seller, rating=4, title=f"Review {i}", comment="Experience.")
            for i in range(8)
        ])
        first = self.client.get(self.url("seller_reviews"))
        second = self.client.get(self.url("seller_reviews"), {"page": "2"})
        self.assertEqual(len(first.context["reviews"]), 6)
        self.assertEqual(len(second.context["reviews"]), 3)
        self.assertEqual(first.context["filtered_count"], 9)
        for page in ["abc", "9999", "-1"]:
            self.assertEqual(self.client.get(self.url("seller_reviews"), {"page": page}).status_code, 200)

    def test_ajax_read_is_partial_and_private(self):
        response = self.client.get(self.url("seller_reviews"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.review.title, response.json()["html"])
        self.assertNotIn("<html", response.json()["html"])
        self.assertIn("no-store", response["Cache-Control"])

    def test_guest_must_login_for_write_routes(self):
        for name in ["create_review", "edit_review", "delete_review", "toggle_helpful", "seller_reply", "delete_reply", "report_review"]:
            response = self.client.post(self.url(name), self.data())
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("login"), response.url)

    def test_create_form_and_valid_post(self):
        self.login()
        self.assertContains(self.client.get(self.url("create_review")), "review-star-input")
        response = self.client.post(self.url("create_review"), self.data(is_friendly="on", is_anonymous="on"))
        self.assertRedirects(response, self.url("seller_reviews"))
        review = Review.objects.get(title="Seller helpful")
        self.assertEqual(review.reviewer, self.buyer)
        self.assertEqual(review.seller, self.seller)
        self.assertTrue(review.is_friendly)
        self.assertTrue(review.is_anonymous)

    def test_create_does_not_trust_posted_owner(self):
        self.login()
        self.client.post(self.url("create_review"), self.data(reviewer=self.other.pk, seller=self.empty_seller.pk))
        review = Review.objects.get(title="Seller helpful")
        self.assertEqual(review.reviewer, self.buyer)
        self.assertEqual(review.seller, self.seller)

    def test_cannot_review_self(self):
        self.login(self.seller)
        for method in ["get", "post"]:
            self.assertEqual(getattr(self.client, method)(self.url("create_review"), self.data()).status_code, 403)

    def test_invalid_create_is_not_saved(self):
        self.login()
        response = self.client.post(self.url("create_review"), self.data(rating=6))
        self.assertTrue(response.context["form"].errors)
        self.assertEqual(Review.objects.count(), 1)

    def test_rating_required_fields_and_lengths(self):
        for extra in [{"rating": 0}, {"rating": 6}, {"rating": "abc"}, {"title": ""},
                      {"title": "x" * 101}, {"comment": ""}, {"comment": "x" * 2001}]:
            with self.subTest(extra=extra):
                self.assertFalse(ReviewForm(data=self.data(**extra)).is_valid())
        self.assertTrue(ReviewForm(data=self.data(title="x" * 100, comment="x" * 2000)).is_valid())

    def test_ajax_create_and_validation(self):
        self.login()
        headers = {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}
        response = self.client.post(self.url("create_review"), self.data(rating=6), **headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn("errorlist", response.json()["html"])
        response = self.client.post(self.url("create_review"), self.data(), **headers)
        self.assertTrue(response.json()["ok"])
        self.assertEqual(response.json()["redirect_url"], self.url("seller_reviews"))

    def test_edit_updates_existing_review(self):
        self.login()
        original_created = self.review.created_at
        response = self.client.get(self.url("edit_review"))
        self.assertContains(response, "Save Changes")
        self.assertEqual(response.context["form"].instance.pk, self.review.pk)
        self.client.post(self.url("edit_review"), self.data())
        self.review.refresh_from_db()
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(self.review.rating, 5)
        self.assertEqual(self.review.created_at, original_created)
        self.assertGreaterEqual(self.review.updated_at, self.review.created_at)

    def test_invalid_edit_preserves_data(self):
        self.login()
        response = self.client.post(self.url("edit_review"), self.data(title=""))
        self.assertTrue(response.context["is_edit"])
        self.review.refresh_from_db()
        self.assertEqual(self.review.title, "Seller ramah")

    def test_other_user_cannot_edit_or_delete(self):
        self.login(self.other)
        for name in ["edit_review", "delete_review"]:
            for method in ["get", "post"]:
                self.assertEqual(getattr(self.client, method)(self.url(name), self.data()).status_code, 404)
        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 4)

    def test_delete_is_post_only_and_preserves_users(self):
        self.login()
        self.review.helpful_by.add(self.other)
        ReviewReport.objects.create(review=self.review, reporter=self.other, reason="spam")
        self.assertEqual(self.client.get(self.url("delete_review")).status_code, 200)
        self.assertTrue(Review.objects.filter(pk=self.review.pk).exists())
        response = self.client.post(self.url("delete_review"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertTrue(response.json()["ok"])
        self.assertFalse(Review.objects.exists())
        self.assertFalse(ReviewReport.objects.exists())
        self.assertTrue(get_user_model().objects.filter(pk=self.seller.pk).exists())

    def test_helpful_toggle(self):
        self.login(self.other)
        for expected in [1, 0, 1]:
            response = self.client.post(self.url("toggle_helpful"), HTTP_X_REQUESTED_WITH="XMLHttpRequest")
            self.assertTrue(response.json()["ok"])
            self.assertEqual(self.review.helpful_by.count(), expected)
        self.assertTrue(self.client.get(self.url("seller_reviews")).context["reviews"][0].has_voted)

    def test_author_and_seller_cannot_vote(self):
        for user in [self.buyer, self.seller]:
            self.login(user)
            self.assertEqual(self.client.post(self.url("toggle_helpful")).status_code, 403)

    def test_seller_reply_create_edit_delete(self):
        self.login(self.seller)
        for text in ["Thank you!", "Updated reply"]:
            self.client.post(self.url("seller_reply"), {"reply": text})
            self.review.refresh_from_db()
            self.assertEqual(self.review.seller_reply, text)
            self.assertIsNotNone(self.review.seller_replied_at)
        self.client.post(self.url("delete_reply"))
        self.review.refresh_from_db()
        self.assertEqual(self.review.seller_reply, "")
        self.assertIsNone(self.review.seller_replied_at)

    def test_only_seller_can_manage_reply(self):
        self.login()
        for name in ["seller_reply", "delete_reply"]:
            self.assertEqual(self.client.post(self.url(name), {"reply": "Fake seller"}).status_code, 404)

    def test_reply_validation_html_and_ajax(self):
        self.login(self.seller)
        for headers in [{}, {"HTTP_X_REQUESTED_WITH": "XMLHttpRequest"}]:
            self.assertEqual(self.client.post(self.url("seller_reply"), {"reply": "x" * 1001}, **headers).status_code, 400)
        self.review.refresh_from_db()
        self.assertEqual(self.review.seller_reply, "")

    def test_report_is_private_and_one_per_user(self):
        self.login(self.other)
        for _ in range(2):
            self.client.post(self.url("report_review"), {"reason": "spam", "details": "Private report note"})
        self.assertEqual(ReviewReport.objects.count(), 1)
        response = self.client.get(self.url("seller_reviews"))
        self.assertNotContains(response, "Private report note")
        self.assertTrue(response.context["reviews"][0].has_reported)

    def test_report_validation(self):
        self.login()
        self.assertEqual(self.client.post(self.url("report_review"), {"reason": "spam"}).status_code, 403)
        self.login(self.other)
        self.assertEqual(self.client.post(self.url("report_review"), {"reason": "fake"}).status_code, 400)
        self.assertFalse(ReviewReport.objects.exists())

    def test_actions_require_post(self):
        self.login(self.seller)
        for name in ["toggle_helpful", "seller_reply", "delete_reply", "report_review"]:
            self.assertEqual(self.client.get(self.url(name)).status_code, 405)

    def test_write_routes_reject_put(self):
        self.login()
        for name in ["create_review", "edit_review", "delete_review"]:
            self.assertEqual(self.client.put(self.url(name)).status_code, 405)

    def test_csrf_is_enforced_for_ajax(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.buyer)
        self.assertEqual(client.post(self.url("create_review"), self.data()).status_code, 403)
        client.get(self.url("create_review"))
        response = client.post(self.url("create_review"), self.data(),
                               HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                               HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value)
        self.assertEqual(response.status_code, 200)

    def test_user_content_is_escaped(self):
        self.review.comment = '<script>alert("xss")</script>'
        self.review.save()
        response = self.client.get(self.url("seller_reviews"))
        self.assertNotContains(response, '<script>alert("xss")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_account_reviews_is_seller_only(self):
        url = reverse("reviews:account_reviews")
        self.assertEqual(self.client.get(url).status_code, 302)
        self.login()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.login(self.seller)
        response = self.client.get(url)
        self.assertContains(response, "Seller Reviews")
        self.assertEqual(response.context["seller"], self.seller)
        self.assertIn("html", self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest").json())

    def test_seller_nav_component_only_for_seller(self):
        template = Template(
            "{% load review_tags %}{% seller_reviews_nav user %}"
        )

        buyer_html = template.render(Context({"user": self.buyer}))
        seller_html = template.render(Context({"user": self.seller}))

        account_url = reverse("reviews:account_reviews")

        self.assertNotIn(account_url, buyer_html)
        self.assertIn(account_url, seller_html)

    def test_seller_rating_component_uses_real_data(self):
        template = Template(
            "{% load review_tags %}{% seller_rating seller %}"
        )

        html = template.render(Context({"seller": self.seller}))

        self.assertIn(self.url("seller_reviews"), html)
        self.assertIn("4.0", html)
        self.assertIn("(1)", html)
        self.assertNotIn("(120)", html)

    def test_database_rejects_invalid_rating_and_self_review(self):
        for kwargs in [{"rating": 6}, {"reviewer": self.seller}]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    Review.objects.create(
                        seller=self.seller, reviewer=kwargs.get("reviewer", self.buyer),
                        rating=kwargs.get("rating", 3), title="Invalid", comment="Invalid.",
                    )

    def test_model_text(self):
        self.assertEqual(str(self.review), f"Review #{self.review.pk} - 4/5")


class ReviewSeedTDDTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.seller = User.objects.create_user(username="seed_seller")
        cls.buyer = User.objects.create_user(username="seed_buyer")
        Product.objects.create(seller=cls.seller, title="Coat", slug="seed-coat", price=100000)
        cls.review = Review.objects.create(reviewer=cls.buyer, seller=cls.seller, rating=4,
                                          title="Seller ramah", comment="Original review.")

    # New behavior written before implementing the seed command.
    def test_seed_is_repeatable_and_preserves_existing_review(self):
        call_command("seed_reviews", seller=self.seller.pk, count=5, verbosity=0)
        call_command("seed_reviews", seller=self.seller.pk, count=5, verbosity=0)
        self.assertEqual(Review.objects.filter(title__startswith="[Demo]").count(), 5)
        self.review.refresh_from_db()
        self.assertEqual(self.review.title, "Seller ramah")

    def test_seed_does_not_impersonate_an_existing_real_account(self):
        get_user_model().objects.create_user(
            username=f"gaia_review_demo_{self.seller.pk}_1", password="temporary-test-password",
        )
        with self.assertRaisesMessage(CommandError, "already belongs"):
            call_command("seed_reviews", seller=self.seller.pk, count=1, verbosity=0)
        self.assertEqual(Review.objects.count(), 1)

    def test_seed_default_adds_fifty_and_rejects_bad_arguments(self):
        for count in [0, 201]:
            with self.assertRaises(CommandError):
                call_command("seed_reviews", seller=self.seller.pk, count=count, verbosity=0)
        with self.assertRaises(CommandError):
            call_command("seed_reviews", seller=999999, verbosity=0)
        call_command("seed_reviews", seller=self.seller.pk, verbosity=0)
        self.assertEqual(Review.objects.filter(title__startswith="[Demo]").count(), 50)

    def test_seed_does_not_reuse_active_passwordless_account(self):
        get_user_model().objects.create_user(username=f"gaia_review_demo_{self.seller.pk}_1")
        with self.assertRaisesMessage(CommandError, "already belongs"):
            call_command("seed_reviews", seller=self.seller.pk, count=1, verbosity=0)
        self.assertEqual(Review.objects.count(), 1)
