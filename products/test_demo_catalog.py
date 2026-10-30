from importlib import import_module
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from products.demo_catalog_v1 import BASE_CATALOG
from products.models import Category, Product, ProductImage


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class HundredDemoProductsTests(TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(TemporaryDirectory()))
        assets = self.base / 'static' / 'images'
        assets.mkdir(parents=True)
        for filename in {row[6] for row in BASE_CATALOG}:
            Image.new('RGB', (4, 4), 'green').save(assets / filename)
        self.enterContext(override_settings(BASE_DIR=self.base, MEDIA_ROOT=self.base / 'media'))
        self.seller = get_user_model().objects.create_user('danariqbalabi', 'demo-seller@example.test')

    def seed(self, **options):
        output = StringIO()
        call_command('seed_demo_products', username=self.seller.username, stdout=output, **options)
        return output.getvalue()

    def test_command_creates_100_complete_demo_products_for_the_selected_seller(self):
        output = self.seed()
        self.assertIn('Created 100 demo products', output)
        self.assertEqual(Product.objects.filter(seller=self.seller).count(), 100)
        self.assertEqual(ProductImage.objects.count(), 100)
        self.assertEqual(Category.objects.count(), 10)
        self.assertEqual(Product.objects.values('slug').distinct().count(), 100)
        self.assertFalse(Product.objects.filter(slug='').exists())
        self.assertFalse(Product.objects.filter(price__lte=0).exists())
        self.assertFalse(Product.objects.exclude(description__startswith='DATA DEMO SINTETIS').exists())
        self.assertFalse(Product.objects.exclude(status='available').exists())
        names = set(ProductImage.objects.values_list('image', flat=True))
        self.assertEqual(len(names), len({row[6] for row in BASE_CATALOG}))
        for name in names:
            photo = ProductImage.objects.filter(image=name).first().image
            self.assertTrue(photo.storage.exists(name))
            with photo.open('rb') as handle:
                Image.open(handle).verify()

    def test_rerun_keeps_real_listings_edits_sold_and_soft_deleted_products(self):
        original = Product.objects.create(seller=self.seller, title='Actual listing', price=99000)
        self.seed()
        sold = Product.objects.exclude(pk=original.pk).first()
        sold.status = 'sold'
        sold.price = 12345
        sold.save()
        deleted = Product.objects.exclude(pk__in=[original.pk, sold.pk]).first()
        deleted.soft_delete()
        ids = set(Product.all_objects.values_list('pk', flat=True))
        names = list(ProductImage.objects.values_list('pk', 'image'))
        self.assertIn('Created 0 demo products', self.seed())
        self.assertEqual(set(Product.all_objects.values_list('pk', flat=True)), ids)
        self.assertEqual(list(ProductImage.objects.values_list('pk', 'image')), names)
        sold.refresh_from_db()
        deleted.refresh_from_db()
        original.refresh_from_db()
        self.assertEqual((sold.status, sold.price), ('sold', 12345))
        self.assertIsNotNone(deleted.deleted_at)
        self.assertEqual(original.price, 99000)

    def test_invalid_count_or_inactive_seller_does_not_write_data(self):
        for count in (0, -1, 101):
            with self.subTest(count=count), self.assertRaises(CommandError):
                self.seed(count=count)
        self.seller.is_active = False
        self.seller.save()
        with self.assertRaises(CommandError):
            self.seed()
        self.assertEqual(Product.all_objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)

    def test_upload_failure_rolls_back_rows_and_cleans_new_images(self):
        storage = ProductImage._meta.get_field('image').storage
        original_save = storage.save
        calls = []
        def broken_save(*args, **kwargs):
            calls.append(1)
            if len(calls) == 2:
                raise OSError('Simulated upload failure')
            return original_save(*args, **kwargs)
        with patch.object(storage, 'save', side_effect=broken_save):
            with self.assertRaises(CommandError):
                self.seed()
        self.assertEqual(Product.all_objects.count(), 0)
        self.assertEqual(ProductImage.objects.count(), 0)
        self.assertEqual(Category.objects.count(), 0)
        self.assertFalse(any(p.is_file() for p in (self.base / 'media').rglob('*')))

    def test_deleting_one_shared_photo_keeps_other_listings_images(self):
        from products.views import _delete_photos
        self.seed()
        first = ProductImage.objects.first()
        storage, name = first.image.storage, first.image.name
        with self.captureOnCommitCallbacks(execute=True):
            _delete_photos([first])
        self.assertTrue(storage.exists(name))
        rest = list(ProductImage.objects.filter(image=name))
        self.assertTrue(rest)
        with self.captureOnCommitCallbacks(execute=True):
            _delete_photos(rest)
        self.assertFalse(storage.exists(name))

    def test_deployment_seed_uses_historical_models_and_is_repeatable(self):
        migration = import_module('products.migrations.0007_seed_100_danar_demo_products')
        apps = MigrationExecutor(connection).loader.project_state().apps
        editor = type('Editor', (), {'connection': connection})()
        migration.seed_danar_catalog(apps, editor)
        migration.seed_danar_catalog(apps, editor)
        self.assertEqual(Product.objects.filter(seller=self.seller).count(), 100)
        self.assertEqual(ProductImage.objects.count(), 100)

    def test_deployment_seed_skips_a_missing_target_without_creating_an_account(self):
        self.seller.username = 'different-owner'
        self.seller.save()
        migration = import_module('products.migrations.0007_seed_100_danar_demo_products')
        apps = MigrationExecutor(connection).loader.project_state().apps
        migration.seed_danar_catalog(apps, type('Editor', (), {'connection': connection})())
        self.assertEqual(Product.objects.count(), 0)
        self.assertFalse(get_user_model().objects.filter(username='danariqbalabi').exists())

    def admin_client(self):
        user = get_user_model().objects.create_superuser('demo-admin', 'demo-admin@example.test', 'test-pw')
        self.client.force_login(user)
        return user

    def test_admin_form_is_read_only_until_a_confirmed_post(self):
        self.admin_client()
        url = reverse('admin:products_product_seed_demo')
        self.assertContains(self.client.get(reverse('admin:products_product_changelist')), 'Add 100 Demo Products')
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(Product.objects.count(), 0)
        self.client.post(url, {'username': self.seller.username})
        self.assertEqual(Product.objects.count(), 0)
        self.assertRedirects(self.client.post(url, {'username': self.seller.username, 'acknowledge': 'on'}),
                             reverse('admin:products_product_changelist'))
        self.assertEqual(Product.objects.filter(seller=self.seller).count(), 100)
        self.client.post(url, {'username': self.seller.username, 'acknowledge': 'on'})
        self.assertEqual(Product.objects.count(), 100)

    def test_seed_admin_view_requires_permissions_and_csrf(self):
        url = reverse('admin:products_product_seed_demo')
        self.assertEqual(self.client.get(url).status_code, 302)
        staff = get_user_model().objects.create_user('unprivileged-staff', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'username': self.seller.username, 'acknowledge': 'on'}).status_code, 403)
        admin = self.admin_client()
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(admin)
        self.assertEqual(strict.post(url, {'username': self.seller.username, 'acknowledge': 'on'}).status_code, 403)
        self.assertEqual(strict.put(url).status_code, 403)
        self.assertEqual(Product.objects.count(), 0)
