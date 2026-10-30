"""Optional browser tests for the product module: manage.py test products.e2e --noinput.

Install reviews/requirements-dev.txt first. Chromium is used, or GAIA_TEST_BROWSER can
point to a locally installed Chrome/Edge executable. No real database is used.
"""
import os
import unittest
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.core.cache import cache
from django.test import Client, override_settings
from django.urls import reverse

from accounts.models import WishlistItem
from .models import Category, Product

try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, "Install requirements-dev.txt to run browser tests.")
@override_settings(ALLOWED_HOSTS=["localhost", "127.0.0.1", "testserver"])
class ProductBrowserTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Playwright's synchronous API owns an event loop in this test thread.
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
        cache.clear()
        User = get_user_model()
        self.seller = User.objects.create_user(username="e2e_seller")
        self.buyer = User.objects.create_user(username="e2e_buyer")
        women = Category.objects.create(name="Women")
        men = Category.objects.create(name="Men")
        self.women_tops = Category.objects.create(name="Tops", parent=women)
        self.men_tops = Category.objects.create(name="Tops", parent=men)
        self.coat = Product.objects.create(seller=self.seller, title="Wool Coat", price=250000, category=self.women_tops)
        self.jacket = Product.objects.create(seller=self.seller, title="Denim Coat Jacket", price=150000, category=self.men_tops)

    def page(self, user=None, *, width=1440):
        context = self.browser.new_context(viewport={"width": width, "height": 1000}, reduced_motion="reduce")
        self.addCleanup(context.close)
        if user:
            client = Client()
            client.force_login(user)
            context.add_cookies([{
                "name": "sessionid", "value": client.cookies["sessionid"].value, "url": self.live_server_url,
            }])
        return context.new_page()

    def url(self, name, *args):
        return self.live_server_url + reverse(name, args=args)

    def mark_page(self, page):
        # A full page load would wipe this marker; HTMX/AJAX updates keep it.
        page.evaluate("window.__noReload = true")

    def assert_no_reload(self, page):
        self.assertTrue(page.evaluate("window.__noReload === true"))

    def test_search_filters_update_results_in_place_with_htmx(self):
        page = self.page()
        page.goto(self.url("products:search") + "?q=coat")
        expect(page.locator("#search-count")).to_have_text("Showing results for 2 products.")
        self.mark_page(page)

        page.locator('label.filter-option:has(input[value="men"])').click()
        expect(page.locator("#search-count")).to_have_text("Showing results for 1 product.")
        expect(page.locator("#search-results .product-card")).to_have_count(1)
        expect(page.locator("#search-results")).to_contain_text("Denim Coat Jacket")
        self.assertIn("gender=men", page.url)

        page.locator('input[name="price_from"]').fill("999999")
        expect(page.locator("#search-results")).to_contain_text("No products match these filters")
        expect(page.locator(".filter-form")).to_be_visible()
        self.assert_no_reload(page)

    def test_guest_adds_and_removes_a_card_from_the_bag_without_reloading(self):
        page = self.page()
        page.goto(self.url("products:home"))
        self.mark_page(page)
        card = page.locator(".product-card", has_text="Wool Coat")
        button = card.get_by_role("button", name="Add to bag")
        button.click()
        expect(card.get_by_role("button", name="Added to bag")).to_have_attribute("aria-pressed", "true")
        expect(page.locator("[data-bag-count]")).to_have_text("1")

        card.get_by_role("button", name="Added to bag").click()
        expect(card.get_by_role("button", name="Add to bag")).to_have_attribute("aria-pressed", "false")
        expect(page.locator("[data-bag-count]")).to_be_hidden()
        self.assert_no_reload(page)

    def test_buyer_saves_and_unsaves_on_the_detail_page(self):
        page = self.page(self.buyer)
        page.goto(self.url("products:detail", self.coat.slug))
        self.mark_page(page)
        page.get_by_role("button", name="Save to wishlist").click()
        expect(page.get_by_role("button", name="Saved to wishlist")).to_be_visible()
        expect(page.locator("[data-wishlist-count]")).to_have_text("1 person has saved this")
        page.wait_for_function("!document.querySelector('[data-wishlist-form]').hasAttribute('aria-busy')")
        self.assertTrue(WishlistItem.objects.filter(user=self.buyer, product_key=self.coat.slug, removed=False).exists())

        page.get_by_role("button", name="Saved to wishlist").click()
        expect(page.get_by_role("button", name="Save to wishlist")).to_be_visible()
        page.wait_for_function("!document.querySelector('[data-wishlist-form]').hasAttribute('aria-busy')")
        self.assertFalse(WishlistItem.objects.filter(user=self.buyer, removed=False).exists())
        self.assert_no_reload(page)

    def test_seller_edits_a_listing(self):
        page = self.page(self.seller)
        page.goto(self.url("products:detail", self.coat.slug))
        page.locator(".pdp-actions").get_by_role("link", name="Edit").click()
        page.locator('input[name="title"]').fill("Wool Coat Long")
        page.get_by_role("button", name="Save changes").click()
        expect(page.locator(".pdp-title")).to_have_text("Wool Coat Long")
        self.coat.refresh_from_db()
        self.assertEqual(self.coat.title, "Wool Coat Long")

    def test_seller_deletes_a_listing_from_its_card_in_place(self):
        page = self.page(self.seller)
        page.goto(self.url("products:picked"))
        self.mark_page(page)
        card = page.locator(".product-card", has_text="Wool Coat")
        card.get_by_role("button", name="Delete Wool Coat").click()
        dialog = page.locator(f"#delete-listing-{self.coat.slug}")
        expect(dialog).to_be_visible()
        dialog.get_by_role("button", name="Delete listing").click()
        expect(card).to_have_count(0)
        expect(page.locator(".toast")).to_contain_text("Listing deleted.")
        self.assert_no_reload(page)
        self.assertFalse(Product.objects.filter(pk=self.coat.pk).exists())

    def test_owner_sees_edit_and_delete_instead_of_buy_buttons(self):
        page = self.page(self.seller)
        page.goto(self.url("products:detail", self.coat.slug))
        expect(page.locator(".pdp-actions").get_by_role("link", name="Edit")).to_be_visible()
        expect(page.locator(".pdp-actions").get_by_role("button", name="Delete")).to_be_visible()
        expect(page.get_by_role("button", name="Add to bag")).to_have_count(0)

    def test_owner_card_buttons_fit_inside_the_card_on_phones(self):
        page = self.page(self.seller, width=375)
        page.goto(self.url("products:picked"))
        card = page.locator(".product-card", has_text="Wool Coat")
        card_box = card.bounding_box()
        for button in [card.get_by_role("button", name="Delete Wool Coat"), card.get_by_role("link", name="Edit")]:
            box = button.bounding_box()
            self.assertGreaterEqual(box["x"], card_box["x"])
            self.assertLessEqual(box["x"] + box["width"], card_box["x"] + card_box["width"])
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth"), 375)
