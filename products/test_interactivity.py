from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, Product


class HtmxSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seller = get_user_model().objects.create_user('htmx-seller')
        women = Category.objects.create(name='Women')
        tops = Category.objects.create(name='Tops', parent=women)
        cls.coat = Product.objects.create(seller=seller, title='Wool Coat', price=200000, category=tops)

    def search(self, **params):
        return self.client.get(reverse('products:search'), {'q': 'coat', **params})

    def test_product_pages_load_htmx_from_static(self):
        self.assertContains(self.search(), 'js/vendor/htmx.min.js')

    def test_filter_form_swaps_only_results_and_count(self):
        response = self.search()
        self.assertContains(response, 'hx-get="%s"' % reverse('products:search'))
        self.assertContains(response, 'hx-target="#search-results"')
        self.assertContains(response, 'hx-select-oob="#search-count"')
        self.assertContains(response, 'hx-push-url="true"')
        self.assertContains(response, 'id="search-results"')
        self.assertContains(response, 'id="search-count"')

    def test_filters_that_match_nothing_keep_the_panel_and_offer_a_reset(self):
        response = self.search(price_from='999999')
        self.assertTrue(response.context['has_matches'])
        self.assertEqual(response.context['result_count'], 0)
        self.assertContains(response, 'class="filter-form"')
        self.assertContains(response, 'No products match these filters')
        self.assertContains(response, 'Showing results for 0 products.')

    def test_a_term_with_no_matches_shows_the_empty_search_page(self):
        response = self.client.get(reverse('products:search'), {'q': 'zzzz'})
        self.assertFalse(response.context['has_matches'])
        self.assertContains(response, 'No result yet')
        self.assertNotContains(response, 'class="filter-form"')

    def test_htmx_request_returns_the_page_with_the_results_region(self):
        response = self.search(HTTP_HX_REQUEST='true', price_to='250000')
        self.assertContains(response, 'id="search-results"')
        self.assertContains(response, 'Wool Coat')


class AjaxDeleteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('ajax-owner')
        cls.product = Product.objects.create(seller=cls.owner, title='Old Boots', price=50000)

    def test_ajax_delete_answers_with_json_and_no_leftover_toast(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('products:delete', args=[self.product.slug]), HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True, 'toast': {'kind': 'added', 'text': 'Listing deleted.'}, 'product_id': self.product.pk})
        self.assertFalse(Product.objects.filter(pk=self.product.pk).exists())
        self.assertNotIn('bag_toast', self.client.session)

    def test_card_delete_dialog_is_wired_for_in_place_removal(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse('products:home'))
        self.assertContains(response, f'aria-controls="delete-listing-{self.product.slug}"')
        self.assertContains(response, f'id="delete-listing-{self.product.slug}"')
