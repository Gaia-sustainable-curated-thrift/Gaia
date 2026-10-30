import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory

from django.template import Context, Template
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


def render(path):
    return Template("{% load asset_version %}{% versioned_static path %}").render(Context({'path': path}))


class VersionedStaticTests(SimpleTestCase):
    def test_existing_file_gets_a_version_number(self):
        self.assertRegex(render('js/gaia.js'), r'^/static/js/gaia\.js\?v=\d+$')

    def test_missing_file_falls_back_to_the_plain_address(self):
        self.assertEqual(render('js/does-not-exist.js'), '/static/js/does-not-exist.js')

    def test_version_changes_when_the_file_changes(self):
        with TemporaryDirectory() as folder, override_settings(STATICFILES_DIRS=[folder]):
            asset = Path(folder) / 'app.js'
            asset.write_text('one')
            os.utime(asset, (1_700_000_000, 1_700_000_000))
            before = render('app.js')
            os.utime(asset, (1_700_000_500, 1_700_000_500))
            after = render('app.js')
        self.assertEqual(before, '/static/app.js?v=1700000000')
        self.assertEqual(after, '/static/app.js?v=1700000500')


class PagesUseVersionedAssetsTests(TestCase):
    def test_shop_pages_load_their_scripts_and_styles_with_a_version(self):
        for name in ['products:home', 'products:picked']:
            html = self.client.get(reverse(name)).content.decode()
            for asset in ['css/gaia.css', 'css/navbar.css', 'js/gaia.js', 'js/products/listing-form.js']:
                with self.subTest(page=name, asset=asset):
                    self.assertRegex(html, re.escape(f'/static/{asset}') + r'\?v=\d+')
        self.assertRegex(self.client.get(reverse('products:home')).content.decode(), r'/static/css/home\.css\?v=\d+')
