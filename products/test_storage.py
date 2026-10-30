import sys
import types
from unittest import mock

from django.core.files.storage import default_storage
from django.test import SimpleTestCase

from .models import ProductImage
from .storage import product_image_storage


class ProductImageStorageTests(SimpleTestCase):
    def test_without_cloudinary_photos_stay_in_local_media(self):
        with mock.patch.dict('os.environ', {'CLOUDINARY_URL': ''}):
            self.assertIs(product_image_storage(), default_storage)

    def test_with_cloudinary_url_photos_use_cloudinary_storage(self):
        class FakeCloudinaryStorage:
            pass

        fake_module = types.ModuleType('cloudinary_storage.storage')
        fake_module.MediaCloudinaryStorage = FakeCloudinaryStorage
        modules = {'cloudinary_storage': types.ModuleType('cloudinary_storage'), 'cloudinary_storage.storage': fake_module}
        with mock.patch.dict('os.environ', {'CLOUDINARY_URL': 'cloudinary://key:secret@demo'}), \
                mock.patch.dict(sys.modules, modules), \
                mock.patch('products.storage._is_test_run', return_value=False):
            self.assertIsInstance(product_image_storage(), FakeCloudinaryStorage)

    def test_cloudinary_is_never_used_while_tests_run(self):
        # .env di laptop bisa berisi CLOUDINARY_URL asli; test tetap harus pakai folder lokal.
        with mock.patch.dict('os.environ', {'CLOUDINARY_URL': 'cloudinary://key:secret@demo'}):
            self.assertIs(product_image_storage(), default_storage)

    def test_product_image_field_uses_the_selector(self):
        field = ProductImage._meta.get_field('image')
        self.assertIs(field._storage_callable, product_image_storage)


class CloudinaryDeleteNameTests(SimpleTestCase):
    def test_delete_uses_the_public_id_for_old_and_new_style_names(self):
        deleted = []

        class FakeBase:
            def _prepend_prefix(self, name):
                return name if name.startswith('media/') else 'media/' + name

            def delete(self, name):
                deleted.append(name)
                return True

        fake_module = types.ModuleType('cloudinary_storage.storage')
        fake_module.MediaCloudinaryStorage = FakeBase
        modules = {'cloudinary_storage': types.ModuleType('cloudinary_storage'), 'cloudinary_storage.storage': fake_module}
        with mock.patch.dict('os.environ', {'CLOUDINARY_URL': 'cloudinary://key:secret@demo'}), \
                mock.patch.dict(sys.modules, modules), \
                mock.patch('products.storage._is_test_run', return_value=False):
            storage = product_image_storage()
            storage.delete('products/2026/10/old-photo.jpg')       # foto lama: tanpa "media/", dengan ekstensi
            storage.delete('media/products/2026/10/new-photo_ab12')  # upload baru: sudah public_id
        self.assertEqual(deleted, ['media/products/2026/10/old-photo', 'media/products/2026/10/new-photo_ab12'])
