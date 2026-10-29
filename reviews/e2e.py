"""Optional browser tests: manage.py test reviews.e2e --noinput.

Install reviews/requirements-dev.txt first. Chromium is used, or GAIA_TEST_BROWSER can
point to a locally installed Chrome/Edge executable. No real database is used.
"""
import os
import re
from pathlib import Path
import unittest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from products.models import Product
from .models import Review, ReviewReport
from accounts.models import AccountOrder
from datetime import date

try:
    from playwright.sync_api import sync_playwright, expect
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, "Install requirements-dev.txt to run browser tests.")
@override_settings(ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"])
class ReviewBrowserTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Playwright's synchronous API owns an event loop in this test thread.
        # Requests and ORM assertions are sequential; this override is test-only.
        guard = patch.dict(os.environ, {"DJANGO_ALLOW_ASYNC_UNSAFE": "true"})
        guard.start()
        cls.addClassCleanup(guard.stop)
        cls.playwright = sync_playwright().start()
        executable = os.getenv("GAIA_TEST_BROWSER")
        cls.browser = cls.playwright.chromium.launch(
            headless=True, **({"executable_path": executable} if executable else {}),
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        super().tearDownClass()

    def setUp(self):
        User = get_user_model()
        self.seller = User.objects.create_user(username="browser_seller", first_name="GAIA SELECT")
        self.author = User.objects.create_user(username="browser_author", first_name="Keisha")
        self.reader = User.objects.create_user(username="browser_reader", first_name="Salma")
        self.product = Product.objects.create(seller=self.seller, title="Vintage coat", slug="browser-coat", price=100000)
        AccountOrder.objects.create(
            user=self.author, seller=self.seller, product=self.product,
            number='BROWSER-VERIFIED', date=date.today(),
            status=AccountOrder.Status.COMPLETED, title=self.product.title,
            subtotal=100000, recipient='Keisha', address='Depok',
        )
        for index, rating in enumerate([4, 4, 3, 5, 5, 4, 3]):
            Review.objects.create(
                reviewer=self.author, seller=self.seller, rating=rating,
                title=f"Experience {index + 1}",
                comment="The seller was friendly and patient with my questions. Communication was clear and helpful.",
                is_anonymous=index == 0, is_friendly=True,
                is_responsive=index % 2 == 0, is_trustworthy=index % 3 == 0,
            )
        self.list_url = self.live_server_url + reverse("reviews:seller_reviews", args=[self.seller.pk])

    def page(self, user=None, *, width=1440, javascript=True):
        context = self.browser.new_context(
            viewport={"width": width, "height": 1000}, java_script_enabled=javascript,
        )
        self.addCleanup(context.close)
        if user:
            client = Client()
            client.force_login(user)
            context.add_cookies([{
                "name": "sessionid", "value": client.cookies["sessionid"].value,
                "url": self.live_server_url,
            }])
        return context.new_page()

    def screenshot(self, page, name):
        directory = os.getenv("GAIA_SCREENSHOT_DIR")
        if directory:
            Path(directory).mkdir(parents=True, exist_ok=True)
            page.evaluate("document.fonts.ready")
            page.screenshot(path=str(Path(directory) / name), full_page=True)

    def test_star_keyboard_and_ajax_crud(self):
        page = self.page(self.author)
        page.goto(self.live_server_url + reverse("reviews:create_review", args=[self.seller.pk]))
        expect(page.get_by_role("heading", name="Write a Seller Review")).to_be_visible()
        self.screenshot(page, "review-form-desktop.png")
        page.locator('label[for="id_rating_2"]').click()
        expect(page.locator("#id_rating_2")).to_be_checked()
        page.locator("#id_rating_2").focus()
        page.keyboard.press("ArrowRight")
        expect(page.locator("#id_rating_3")).to_be_checked()
        page.get_by_label("Experience summary").fill("Browser-created review")
        page.get_by_label("Share your experience").fill("A clear and friendly experience.")
        page.get_by_text("Friendly & polite", exact=True).click()
        with page.expect_response(lambda response: response.request.method == "POST" and "/create/" in response.url) as action:
            page.get_by_role("button", name="Submit Seller Review").click()
        self.assertEqual(action.value.headers["content-type"], "application/json")
        expect(page).to_have_url(self.list_url)
        card = page.locator(".seller-review").filter(has_text="Browser-created review")
        expect(card).to_be_visible()
        expect(card.locator(".review-verified")).to_have_text("\u2713 Verified buyer")
        expect(page.get_by_role('link', name='Rate Seller', exact=True)).to_have_count(0)
        expect(page.locator('.seller-context').get_by_role('link', name='Edit My Review', exact=True)).to_be_visible()
        self.screenshot(page, "verified-review-desktop.png")
        card.get_by_role("link", name="Edit Review").click()
        expect(page.get_by_label("Experience summary")).to_have_value("Browser-created review")
        page.get_by_label("Experience summary").fill("Browser-updated review")
        page.get_by_role("button", name="Save Changes").click()
        expect(page).to_have_url(self.list_url)
        card = page.locator(".seller-review").filter(has_text="Browser-updated review")
        card.get_by_role("link", name="Delete Review").click()
        expect(page.get_by_role("heading", name="Delete Review", exact=True)).to_be_visible()
        page.get_by_role("button", name="Yes, Delete Review").click()
        expect(page).to_have_url(self.list_url)
        self.assertFalse(Review.objects.filter(title="Browser-updated review").exists())

    def test_ajax_filter_helpful_report_and_seller_reply(self):
        page = self.page(self.reader)
        page.goto(self.list_url)
        self.screenshot(page, "seller-reviews-desktop.png")
        page.evaluate("window.reviewTestMarker = 42")
        page.locator('.review-filters a[href*="rating=3"]').click()
        expect(page.locator(".seller-review")).to_have_count(2)
        self.assertEqual(page.evaluate("window.reviewTestMarker"), 42)
        expect(page.locator(".rating-score")).to_contain_text("7 seller reviews")
        page.get_by_role("link", name="Rating", exact=True).click()
        expect(page).to_have_url(self.list_url + "?sort=rating&rating=3")
        expect(page.locator(".seller-review")).to_have_count(2)
        page.get_by_role("link", name="All", exact=True).click()
        expect(page.locator(".seller-review")).to_have_count(6)
        first = page.locator(".seller-review").first
        first.locator('form[action$="/helpful/"] button').click()
        expect(first.locator('form[action$="/helpful/"] button')).to_have_text("Helpful (1)")
        self.assertEqual(page.evaluate("window.reviewTestMarker"), 42)
        first.locator("details summary").click()
        first.locator('select[name="reason"]').select_option("spam")
        first.locator('textarea[name="details"]').fill("Browser-only private report.")
        first.get_by_role("button", name="Send report").click()
        expect(first).to_contain_text("Reported")
        self.assertEqual(ReviewReport.objects.count(), 1)
        expect(page.locator("[data-review-panel]")).not_to_contain_text("Browser-only private report.")

        seller_page = self.page(self.seller)
        seller_page.goto(self.list_url)
        first = seller_page.locator(".seller-review").first
        first.get_by_text("Reply to review", exact=True).click()
        first.locator('textarea[name="reply"]').fill("Thank you for your trust.")
        first.get_by_role("button", name="Save reply").click()
        expect(first.locator(".seller-reply")).to_contain_text("Thank you for your trust.")
        seller_page.goto(self.live_server_url + reverse("reviews:account_reviews"))
        expect(
            seller_page.get_by_role(
                "heading",
                name="Seller Reviews",
                exact=True,
            )
        ).to_be_visible()
        self.screenshot(seller_page, "seller-account-reviews.png")

    def test_mobile_guest_and_no_javascript_fallback(self):
        page = self.page(width=390)
        page.goto(self.list_url)
        expect(page.locator(".reviewer-name").first).to_have_text("GAIA member")
        self.assertFalse(page.evaluate("document.documentElement.scrollWidth > innerWidth"))
        self.screenshot(page, "seller-reviews-mobile.png")
        page.get_by_role("link", name="Rate Seller").click()
        expect(page).to_have_url(re.compile(r"/accounts/login/"))
        mobile_form = self.page(self.author, width=390)
        mobile_form.goto(self.live_server_url + reverse("reviews:create_review", args=[self.seller.pk]))
        self.assertFalse(mobile_form.evaluate("document.documentElement.scrollWidth > innerWidth"))
        self.screenshot(mobile_form, "review-form-mobile.png")

        plain = self.page(self.author, javascript=False)
        plain.goto(self.live_server_url + reverse("reviews:create_review", args=[self.seller.pk]))
        plain.locator('label[for="id_rating_4"]').click()
        plain.get_by_label("Experience summary").fill("No-JS review")
        plain.get_by_label("Share your experience").fill("Normal HTML form submission still works.")
        plain.get_by_role("button", name="Submit Seller Review").click()
        expect(plain).to_have_url(self.list_url)
        self.assertTrue(Review.objects.filter(title="No-JS review").exists())

    def test_ajax_network_failure_has_feedback(self):
        page = self.page(self.reader)
        page.goto(self.list_url)
        page.route("**/reviews/*/helpful/", lambda route: route.abort())
        page.locator('form[action$="/helpful/"] button').first.click()
        expect(page.locator("[data-review-status]")).to_be_visible()
        expect(page.locator("[data-review-status]")).to_have_class("review-status is-error")
        expect(page.locator('form[action$="/helpful/"] button').first).to_be_enabled()
