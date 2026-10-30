import sys
import types
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from .models import Product, ProductImage


class FakeCloudinary:
    """Cloudinary tiruan: mencatat apa yang diunggah, tanpa internet."""

    def __init__(self, already_there=(), cdn_lag=False):
        self.remote = set(already_there)
        self.uploads = []
        # cdn_lag: foto sudah terunggah tapi alamatnya belum bisa dibuka (CDN belum menyebar).
        self.cdn_lag = cdn_lag

    def modules(self):
        outer = self

        class FakeStorage:
            TAG = 'media'

            def _prepend_prefix(self, name):
                return name if name.startswith('media/') else 'media/' + name

            def exists(self, name):
                return name in outer.remote

        def upload(path, **options):
            outer.uploads.append((Path(path).name, options['public_id']))
            if not outer.cdn_lag:
                # Di database namanya tanpa awalan "media/", jadi disimpan seperti itu.
                outer.remote.add(options['public_id'].removeprefix('media/') + '.png')

        storage_module = types.ModuleType('cloudinary_storage.storage')
        storage_module.MediaCloudinaryStorage = FakeStorage
        uploader = types.ModuleType('cloudinary.uploader')
        uploader.upload = upload
        cloudinary = types.ModuleType('cloudinary')
        cloudinary.uploader = uploader
        return {
            'cloudinary': cloudinary,
            'cloudinary.uploader': uploader,
            'cloudinary_storage': types.ModuleType('cloudinary_storage'),
            'cloudinary_storage.storage': storage_module,
        }


class UploadPhotosToCloudinaryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seller = get_user_model().objects.create_user('cloud-seller')
        product = Product.objects.create(seller=seller, title='Cloud Coat', price=100000)
        cls.here = ProductImage.objects.create(product=product, image='products/2026/10/here.png')
        cls.gone = ProductImage.objects.create(product=product, image='products/2026/10/gone.png')

    def setUp(self):
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        folder = Path(media.name) / 'products' / '2026' / '10'
        folder.mkdir(parents=True)
        (folder / 'here.png').write_bytes(b'png')
        self.media_root = media.name

    def run_command(self, fake, **options):
        out = StringIO()
        with override_settings(MEDIA_ROOT=self.media_root), \
                mock.patch.dict('os.environ', {'CLOUDINARY_URL': 'cloudinary://key:secret@demo'}), \
                mock.patch.dict(sys.modules, fake.modules()):
            call_command('upload_photos_to_cloudinary', stdout=out, **options)
        return out.getvalue()

    def test_needs_cloudinary_url(self):
        with mock.patch.dict('os.environ', {'CLOUDINARY_URL': ''}), self.assertRaisesMessage(CommandError, 'CLOUDINARY_URL'):
            call_command('upload_photos_to_cloudinary', stdout=StringIO())

    def test_uploads_local_photos_with_a_public_id_that_matches_the_database_name(self):
        fake = FakeCloudinary()
        output = self.run_command(fake)
        self.assertEqual(fake.uploads, [('here.png', 'media/products/2026/10/here')])
        self.assertIn('1 diunggah, 0 sudah ada', output)

    def test_files_missing_from_media_are_reported_not_fatal(self):
        output = self.run_command(FakeCloudinary())
        self.assertIn('1 tidak ditemukan di media/', output)
        self.assertIn('products/2026/10/gone.png', output)

    def test_photos_already_on_cloudinary_are_skipped(self):
        fake = FakeCloudinary(already_there={'products/2026/10/here.png'})
        output = self.run_command(fake)
        self.assertEqual(fake.uploads, [])
        self.assertIn('0 diunggah, 1 sudah ada', output)

    def test_dry_run_uploads_nothing(self):
        fake = FakeCloudinary()
        output = self.run_command(fake, dry_run=True)
        self.assertEqual(fake.uploads, [])
        self.assertIn('[dry-run] Unggah products/2026/10/here.png', output)

    def test_warns_when_a_fresh_upload_cannot_be_opened_yet(self):
        fake = FakeCloudinary(cdn_lag=True)
        with mock.patch('products.management.commands.upload_photos_to_cloudinary.time.sleep'):
            output = self.run_command(fake)
        self.assertEqual(len(fake.uploads), 1)
        self.assertIn('belum bisa dibuka', output)
