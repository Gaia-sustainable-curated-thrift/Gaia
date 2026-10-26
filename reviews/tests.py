from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import ReviewForm
from .models import Review


class ReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.seller = User.objects.create_user(username="test_seller")
        cls.buyer = User.objects.create_user(username="test_buyer")
        cls.other_user = User.objects.create_user(username="other_user")

        cls.review = Review.objects.create(
            reviewer=cls.buyer,
            seller=cls.seller,
            rating=4,
            title="Seller ramah",
            comment="Barang sesuai deskripsi.",
        )

    def test_guest_must_login_to_create_review(self):
        url = reverse(
            "reviews:create_review",
            args=[self.seller.pk],
        )

        response = self.client.get(url)

        self.assertRedirects(
            response,
            f"{reverse('login')}?next={url}",
            fetch_redirect_response=False,
        )

    def test_rating_outside_range_is_invalid(self):
        for rating in [0, 6]:
            with self.subTest(rating=rating):
                form = ReviewForm(data={
                    "rating": rating,
                    "title": "Review percobaan",
                    "comment": "Komentar percobaan.",
                })

                self.assertFalse(form.is_valid())
                self.assertIn("rating", form.errors)

    def test_other_user_cannot_edit_review(self):
        self.client.force_login(self.other_user)

        url = reverse(
            "reviews:edit_review",
            args=[self.review.pk],
        )

        response = self.client.post(url, {
            "rating": 1,
            "title": "Diubah orang lain",
            "comment": "Komentar diubah.",
        })

        self.assertEqual(response.status_code, 404)

        self.review.refresh_from_db()
        self.assertEqual(self.review.rating, 4)
        self.assertEqual(self.review.title, "Seller ramah")

    def test_other_user_cannot_delete_review(self):
        self.client.force_login(self.other_user)

        url = reverse(
            "reviews:delete_review",
            args=[self.review.pk],
        )

        response = self.client.post(url)

        self.assertEqual(response.status_code, 404)
        self.assertTrue(
            Review.objects.filter(pk=self.review.pk).exists()
        )