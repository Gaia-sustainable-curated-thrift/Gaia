"""Browser regression tests: python manage.py test accounts.e2e --noinput."""
import io
import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import Client, override_settings
from django.urls import reverse
from accounts.models import Profile, WishlistItem
try:
    from playwright.sync_api import expect, sync_playwright
except ImportError:
    sync_playwright = None


@unittest.skipUnless(sync_playwright, 'Install Playwright to run account browser tests.')
@override_settings(ALLOWED_HOSTS=['localhost', '127.0.0.1', 'testserver'],
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
                   PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class AccountBrowserTests(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.async_guard = patch.dict(os.environ, {'DJANGO_ALLOW_ASYNC_UNSAFE': 'true'})
        cls.async_guard.start()
        cls.playwright = sync_playwright().start()
        executable = os.getenv('GAIA_TEST_BROWSER')
        cls.browser = cls.playwright.chromium.launch(headless=True, **({'executable_path': executable} if executable else {}))

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()
        cls.async_guard.stop()
        super().tearDownClass()

    def setUp(self):
        self.media = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=self.media))
        self.user = get_user_model().objects.create_user('browser-owner', 'browser@example.test', 'Circular!Fashion2026', first_name='Browser Owner')
        Profile.objects.create(user=self.user, phone='08123456789', city='Jakarta', country='Indonesia')
        self.item = WishlistItem.objects.create(user=self.user, product_key='browser-coat', title='Browser Coat', price=100000)

    def page(self, user=None, width=1440, javascript=True):
        context = self.browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=javascript,
                                           reduced_motion='reduce')
        self.addCleanup(context.close)
        if user:
            client = Client()
            client.force_login(user)
            context.add_cookies([{'name': 'sessionid', 'value': client.cookies['sessionid'].value, 'url': self.live_server_url}])
        return context.new_page()

    def url(self, name, *args):
        return self.live_server_url + reverse(name, args=args)

    def mark(self, page):
        page.evaluate('window.__accountNoReload = true')

    def assert_preserved(self, page):
        self.assertTrue(page.evaluate('window.__accountNoReload === true'))

    def test_register_login_and_profile_navigation_use_ajax(self):
        page = self.page()
        page.goto(self.url('register'))
        self.mark(page)
        page.locator('[name=full_name]').fill('New Browser Member')
        page.locator('[name=email]').fill('new-browser@example.test')
        page.locator('[name=password1]').fill('Circular!Fashion2026')
        page.locator('[name=password2]').fill('Circular!Fashion2026')
        page.get_by_role('button', name='Create Account', exact=True).click()
        expect(page).to_have_url(self.url('account_created'))
        self.assert_preserved(page)
        page.get_by_role('link', name='Continue to Profile').click()
        expect(page).to_have_url(self.url('profile'))
        self.assert_preserved(page)
        page.get_by_role('link', name='Edit Profile', exact=True).click()
        expect(page.locator('[name=phone]')).to_be_visible()
        self.assert_preserved(page)
        self.assertTrue(get_user_model().objects.filter(email='new-browser@example.test').exists())

    def test_login_errors_and_success_do_not_reload(self):
        page = self.page()
        page.goto(self.url('login'))
        self.mark(page)
        page.locator('[name=username]').fill(self.user.email)
        page.locator('[name=password]').fill('wrong-password')
        page.get_by_role('button', name='Log In', exact=True).click()
        expect(page.locator('.errorlist').first).to_be_visible()
        self.assert_preserved(page)
        page.locator('[name=password]').fill('Circular!Fashion2026')
        page.get_by_role('button', name='Log In', exact=True).click()
        expect(page).to_have_url(self.url('profile'))
        self.assert_preserved(page)

    def test_profile_validation_avatar_and_save_work_without_reload_on_mobile(self):
        page = self.page(self.user, width=390)
        page.goto(self.url('edit_profile'))
        self.mark(page)
        page.locator('[name=username]').fill('gaiacare')
        page.get_by_role('button', name='Save Changes').click()
        expect(page.locator('.errorlist').first).to_contain_text('reserved')
        self.assert_preserved(page)
        page.locator('[name=username]').fill('browser-updated')
        page.locator('[name=city]').fill('Bandung')
        image = io.BytesIO()
        Image.new('RGB', (50, 60), 'green').save(image, format='PNG')
        page.locator('[name=avatar]').set_input_files({'name': 'profile.png', 'mimeType': 'image/png', 'buffer': image.getvalue()})
        expect(page.locator('[data-avatar-preview]')).to_be_visible()
        page.get_by_role('button', name='Save Changes').click()
        expect(page).to_have_url(self.url('profile'))
        expect(page.locator('main')).to_contain_text('Bandung')
        self.assert_preserved(page)
        self.user.refresh_from_db()
        self.assertTrue(self.user.profile.avatar)
        self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
        page.get_by_role('link', name='Edit Profile', exact=True).click()
        expect(page.locator('[name=city]')).to_have_value('Bandung')
        self.assert_preserved(page)

    def test_wishlist_remove_undo_and_pagination_keep_the_document(self):
        for index in range(13):
            WishlistItem.objects.create(user=self.user, product_key=f'page-{index}', title=f'Page Item {index}', price=1)
        page = self.page(self.user)
        page.goto(self.url('wishlist'))
        self.mark(page)
        page.get_by_role('link', name='Next', exact=False).click()
        expect(page).to_have_url(self.url('wishlist') + '?page=2')
        page.get_by_role('button', name='Remove from Wishlist').first.click()
        expect(page.get_by_role('button', name='Undo Removal')).to_be_visible()
        self.assert_preserved(page)
        page.get_by_role('button', name='Undo Removal').click()
        expect(page.locator('.wishlist-card')).to_have_count(2)
        self.assert_preserved(page)

    def test_delete_account_requires_confirmation_and_finishes_without_reload(self):
        page = self.page(self.user)
        page.goto(self.url('delete_account'))
        self.mark(page)
        page.locator('[name=password]').fill('wrong-password')
        page.locator('[name=confirmation]').fill('DELETE')
        page.locator('[name=acknowledge]').check()
        page.get_by_role('button', name='Permanently Delete Account').click()
        expect(page.locator('.errorlist').first).to_contain_text('incorrect')
        self.assert_preserved(page)
        page.locator('[name=password]').fill('Circular!Fashion2026')
        page.get_by_role('button', name='Permanently Delete Account').click()
        expect(page).to_have_url(self.url('login'))
        self.assert_preserved(page)
        self.assertFalse(get_user_model().objects.filter(pk=self.user.pk).exists())

    def test_network_failure_keeps_input_and_allows_retry(self):
        page = self.page(self.user)
        page.goto(self.url('edit_profile'))
        page.locator('[name=city]').fill('Surabaya')
        page.route('**/accounts/profile/edit/', lambda route: route.abort())
        page.get_by_role('button', name='Save Changes').click()
        expect(page.locator('#account-request-status')).to_have_class('account-request-status account-request-error')
        expect(page.locator('[name=city]')).to_have_value('Surabaya')
        page.unroute('**/accounts/profile/edit/')
        page.get_by_role('button', name='Save Changes').click()
        expect(page).to_have_url(self.url('profile'))

    def test_standard_html_form_still_works_without_javascript(self):
        page = self.page(self.user, javascript=False)
        page.goto(self.url('edit_profile'))
        page.locator('[name=city]').fill('Depok')
        page.get_by_role('button', name='Save Changes').click()
        expect(page).to_have_url(self.url('profile'))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.city, 'Depok')

    def test_browser_cannot_remove_another_users_wishlist_item(self):
        other = get_user_model().objects.create_user('other-browser')
        item = WishlistItem.objects.create(user=other, product_key='private', title='Private Item', price=1)
        page = self.page(self.user)
        page.goto(self.url('wishlist'))
        token = page.locator('[name=csrfmiddlewaretoken]').first.input_value()
        response = page.request.post(self.url('wishlist_remove', item.pk), form={'csrfmiddlewaretoken': token})
        self.assertEqual(response.status, 404)
        item.refresh_from_db()
        self.assertFalse(item.removed)


    def test_my_products_delete_dialog_keeps_document_and_updates_list(self):
        from products.models import Product
        product = Product.objects.create(seller=self.user, title='Browser Listing', price=50000)
        page = self.page(self.user)
        page.goto(self.url('my_products'))
        self.mark(page)
        page.locator('[data-product-delete-url]').click()
        expect(page.locator('#my-product-delete-dialog')).to_be_visible()
        page.locator('#my-product-delete-dialog').get_by_role('button', name='Delete Listing', exact=True).click()
        expect(page.get_by_role('heading', name='Your first listing starts here')).to_be_visible()
        self.assert_preserved(page)
        self.assertFalse(Product.objects.filter(pk=product.pk).exists())

    def test_expired_csrf_shows_error_without_losing_input(self):
        page = self.page(self.user)
        page.goto(self.url('edit_profile'))
        self.mark(page)
        page.locator('[name=city]').fill('Surabaya')
        page.evaluate("document.querySelector('main [name=csrfmiddlewaretoken]').value = 'bad-token'")
        page.get_by_role('button', name='Save Changes').click()
        expect(page.locator('#account-request-status')).to_contain_text('security token has expired')
        expect(page.locator('[name=city]')).to_have_value('Surabaya')
        self.assert_preserved(page)

    def test_password_change_and_logout_work_after_ajax_navigation(self):
        page = self.page(self.user)
        page.goto(self.url('account_settings'))
        self.mark(page)
        page.get_by_role('link', name='Change Password', exact=True).click()
        expect(page).to_have_url(self.url('password_change'))
        page.locator('[name=old_password]').fill('Circular!Fashion2026')
        page.locator('[name=new_password1]').fill('Second!Circular2027')
        page.locator('[name=new_password2]').fill('Second!Circular2027')
        page.get_by_role('button', name='Save Password').click()
        expect(page).to_have_url(self.url('account_settings'))
        self.assert_preserved(page)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Second!Circular2027'))
        page.locator('main [data-logout]').first.click()
        page.get_by_role('button', name='Yes, Log Out').click()
        expect(page).to_have_url(self.url('login'))
        self.assert_preserved(page)

    def test_resend_verification_preserves_document_and_reports_cooldown(self):
        page = self.page(self.user)
        page.goto(self.url('account_settings'))
        self.mark(page)
        page.get_by_role('button', name='Resend Verification Email').click()
        expect(page.locator('main')).to_contain_text('Verification email sent.')
        self.assert_preserved(page)
        page.get_by_role('button', name='Resend Verification Email').click()
        expect(page.locator('main')).to_contain_text('Please wait one minute')
        self.assert_preserved(page)


    def test_bag_remove_works_after_login_rotates_csrf(self):
        from products.models import Product
        seller = get_user_model().objects.create_user('bag-seller')
        product = Product.objects.create(seller=seller, title='Bag Test Coat', price=10)
        page = self.page()
        page.goto(self.url('login'))
        token = page.locator('main [name=csrfmiddlewaretoken]').input_value()
        page.request.post(self.url('products:bag_add', product.slug), form={'csrfmiddlewaretoken': token})
        page.goto(self.url('login'))
        page.locator('[name=username]').fill(self.user.email)
        page.locator('[name=password]').fill('Circular!Fashion2026')
        page.get_by_role('button', name='Log In', exact=True).click()
        expect(page).to_have_url(self.url('profile'))
        page.locator('.gaia-navbar [data-bag-toggle]').click()
        with page.expect_response(lambda response: reverse('products:bag_set', args=[product.slug]) in response.url) as result:
            page.locator('#bag-drawer').get_by_role('button', name='Remove Bag Test Coat from bag').click()
        self.assertEqual(result.value.status, 200)
        expect(page.locator('#bag-drawer .bag-item')).to_have_count(0)

    def test_back_cancels_pending_navigation_and_ignores_its_response(self):
        page = self.page(self.user)
        page.goto(self.url('profile'))
        self.mark(page)
        page.get_by_role('link', name='Edit Profile', exact=True).click()
        expect(page).to_have_url(self.url('edit_profile'))
        routes = []
        page.route('**/accounts/settings/', lambda route: routes.append(route))
        page.locator('main').get_by_role('link', name='Account Settings', exact=True).click()
        page.wait_for_timeout(150)
        page.go_back()
        expect(page).to_have_url(self.url('profile'))
        expect(page.get_by_role('link', name='Edit Profile', exact=True)).to_be_visible()
        self.assert_preserved(page)
        page.wait_for_timeout(200)
        expect(page).to_have_url(self.url('profile'))
        for route in routes:
            try:
                route.abort()
            except Exception:
                pass
        page.unroute('**/accounts/settings/')


    def test_seller_can_open_sales_and_detail_without_reload_or_admin_controls(self):
        from accounts.models import AccountOrder
        from datetime import date
        buyer = get_user_model().objects.create_user('sales-browser-buyer')
        order = AccountOrder.objects.create(user=buyer, seller=self.user, number='BROWSER-SALE', date=date.today(),
            status='awaiting_payment', title='Browser Sale Coat', subtotal=100, recipient='Buyer', address='Depok')
        page = self.page(self.user, width=390)
        page.goto(self.url('orders'))
        self.mark(page)
        page.get_by_role('link', name='My Sales', exact=True).click()
        expect(page).to_have_url(self.url('orders') + '?scope=sales')
        expect(page.locator('main')).to_contain_text(order.number)
        page.get_by_role('link', name='View Details', exact=True).click()
        expect(page).to_have_url(self.url('order_detail', order.pk))
        expect(page.locator('main')).to_contain_text('Sale to')
        expect(page.get_by_role('button', name='Confirm Payment Received')).to_have_count(0)
        self.assert_preserved(page)
        page.get_by_role('link', name='Back to Orders', exact=True).click()
        expect(page).to_have_url(self.url('orders') + '?scope=sales')
