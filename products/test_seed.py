from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .models import Category, Product, ProductImage


class SeedProductsTests(TestCase):
    def setUp(self):
        self.seller = get_user_model().objects.create_user('seed-seller')

        # Both the sample picture and saved uploads live outside the real project.
        self.base = Path(self.enterContext(TemporaryDirectory()))
        self.sample = self.base / 'static' / 'images' / 'reference-coat.png'
        self.sample.parent.mkdir(parents=True)
        Image.new('RGB', (4, 4), 'green').save(self.sample)
        self.enterContext(override_settings(BASE_DIR=self.base, MEDIA_ROOT=self.base / 'media'))

    def seed(self, **options):
        output = StringIO()
        call_command('seed_products', stdout=output, **options)
        return output.getvalue()

    def test_explicit_username_builds_catalog_for_the_chosen_seller(self):
        get_user_model().objects.create_superuser('admin', 'admin@example.test')
        output = self.seed(username=self.seller.username)

        parents = Category.objects.filter(parent__isnull=True)
        self.assertEqual(set(parents.values_list('name', flat=True)), {'Women', 'Men'})
        self.assertEqual(Category.objects.count(), 10)
        for parent in parents:
            with self.subTest(department=parent.name):
                self.assertEqual(set(parent.children.values_list('name', flat=True)), {'Tops', 'Bottoms', 'Shoes', 'Bags'})
                self.assertTrue(all(child.slug.startswith(parent.slug + '-') for child in parent.children.all()))

        self.assertEqual(Product.objects.count(), 4)
        self.assertEqual(set(Product.objects.values_list('seller_id', flat=True)), {self.seller.pk})
        self.assertFalse(Product.objects.filter(category__isnull=True).exists())
        self.assertFalse(Product.objects.filter(price__lte=0).exists())
        self.assertEqual(Product.objects.filter(status=Product.Status.SOLD).count(), 1)
        self.assertIn('Demo products seeded.', output)

    def test_default_seller_is_the_first_superuser(self):
        first = get_user_model().objects.create_superuser('first-admin', 'first@example.test')
        get_user_model().objects.create_superuser('second-admin', 'second@example.test')

        self.seed()

        self.assertEqual(Product.objects.count(), 4)
        self.assertEqual(set(Product.objects.values_list('seller_id', flat=True)), {first.pk})

    def test_unknown_username_fails_without_creating_catalog_data(self):
        with self.assertRaisesMessage(CommandError, 'Create the seller account first.'):
            self.seed(username='missing-seller')

        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(ProductImage.objects.count(), 0)

    def test_no_superuser_requires_an_explicit_seller(self):
        with self.assertRaisesMessage(CommandError, 'No superuser found.'):
            self.seed()

        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Product.objects.count(), 0)

    def test_rerunning_seed_preserves_existing_categories_products_and_images(self):
        women = Category.objects.create(name='Women')
        tops = Category.objects.create(name='Tops', parent=women)
        original = Product.objects.create(seller=self.seller, title='My Original Listing', category=tops, price=75000)
        self.seed(username=self.seller.username)
        seeded = Product.objects.exclude(pk=original.pk).first()
        seeded.price = 123456
        seeded.status = Product.Status.SOLD
        seeded.save()
        product_ids = set(Product.objects.values_list('pk', flat=True))
        images = list(ProductImage.objects.values_list('pk', 'image'))

        self.seed(username=self.seller.username)

        self.assertEqual(Category.objects.count(), 10)
        self.assertEqual(Category.objects.get(slug='women').pk, women.pk)
        self.assertEqual(Category.objects.get(slug='women-tops').pk, tops.pk)
        self.assertEqual(set(Product.objects.values_list('pk', flat=True)), product_ids)
        self.assertEqual(list(ProductImage.objects.values_list('pk', 'image')), images)
        original.refresh_from_db()
        seeded.refresh_from_db()
        self.assertEqual(original.price, 75000)
        self.assertEqual(seeded.price, 123456)
        self.assertEqual(seeded.status, Product.Status.SOLD)

    def test_sample_images_are_saved_as_primary_images_in_test_storage(self):
        self.seed(username=self.seller.username)

        self.assertEqual(ProductImage.objects.count(), 4)
        for product in Product.objects.all():
            with self.subTest(product=product.title):
                self.assertEqual(product.images.count(), 1)
                photo = product.images.get()
                self.assertTrue(photo.is_primary)
                self.assertEqual(product.primary_image, photo)
                self.assertTrue(photo.image.storage.exists(photo.image.name))
                self.assertTrue(photo.image.path.startswith(str(self.base / 'media')))
                with photo.image.open('rb') as stored:
                    with Image.open(stored) as image:
                        self.assertEqual(image.format, 'PNG')
                        image.verify()

    def test_missing_sample_picture_does_not_prevent_catalog_creation(self):
        self.sample.unlink()

        output = self.seed(username=self.seller.username)

        self.assertEqual(Category.objects.count(), 10)
        self.assertEqual(Product.objects.count(), 4)
        self.assertEqual(ProductImage.objects.count(), 0)
        self.assertIn('Demo products seeded.', output)
