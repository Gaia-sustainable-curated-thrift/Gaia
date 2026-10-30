from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, TestCase
from .environment import security_settings


class DeploymentSettingsTests(SimpleTestCase):
    def test_production_requires_a_new_strong_secret(self):
        for key in ('', 'short', 'a' * 60, 'django-insecure-' + 'abcdef' * 10):
            with self.subTest(key_length=len(key)), self.assertRaises(ImproperlyConfigured):
                security_settings({'PRODUCTION': 'True', 'SECRET_KEY': key})

    def test_production_enforces_https_without_debug(self):
        config = security_settings({'PRODUCTION': 'True', 'SECRET_KEY': 'abcdefghij0123456789' * 3})
        self.assertFalse(config['DEBUG'])
        for name in ('SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE', 'SECURE_SSL_REDIRECT'):
            self.assertTrue(config[name])
        self.assertEqual(config['SECURE_PROXY_SSL_HEADER'], ('HTTP_X_FORWARDED_PROTO', 'https'))
        self.assertGreater(config['SECURE_HSTS_SECONDS'], 0)

    def test_local_development_still_accepts_http(self):
        config = security_settings({})
        self.assertTrue(config['DEBUG'])
        self.assertFalse(config['SECURE_SSL_REDIRECT'])
        self.assertIsNone(config['SECURE_PROXY_SSL_HEADER'])
        self.assertGreaterEqual(len(config['SECRET_KEY']), 50)


class ProductionMediaTests(TestCase):
    def setUp(self):
        from tempfile import TemporaryDirectory
        from django.test import override_settings
        self.directory = TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name, DEBUG=False)
        self.settings_override.enable()
        self.addCleanup(self.directory.cleanup)
        self.addCleanup(self.settings_override.disable)

    def save_image(self, name):
        from io import BytesIO
        from PIL import Image
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        content = BytesIO()
        Image.new('RGB', (4, 4), 'green').save(content, format='PNG')
        return default_storage.save(name, ContentFile(content.getvalue()))

    def test_valid_uploads_work_without_debug_and_use_detected_content_type(self):
        name = self.save_image('products/coat.jpg')
        response = self.client.get('/media/' + name)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'image/png')
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertTrue(b''.join(response.streaming_content).startswith(b'\x89PNG'))
        finally:
            response.close()
        response = self.client.head('/media/' + name)
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_html_svg_and_missing_files_are_not_served_as_uploads(self):
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        for name, body in [('products/fake.jpg', b'<html>bad</html>'), ('chat/fake.html', b'<html>bad</html>'),
                           ('avatars/fake.svg', b'<svg xmlns="http://www.w3.org/2000/svg"></svg>')]:
            default_storage.save(name, ContentFile(body))
            self.assertEqual(self.client.get('/media/' + name).status_code, 404)
        self.assertEqual(self.client.get('/media/products/missing.jpg').status_code, 404)

    def test_path_traversal_and_unknown_roots_are_rejected(self):
        from django.http import Http404
        from django.test import RequestFactory
        from .media import uploaded_image
        for name in ('../settings.py', '/etc/passwd', 'products/../../settings.py', 'private/secret.png'):
            with self.subTest(name=name), self.assertRaises(Http404):
                uploaded_image(RequestFactory().get('/media/test'), name)

    def test_chat_uploads_require_a_conversation_participant(self):
        from django.contrib.auth import get_user_model
        from chat.models import Conversation, Message
        from products.models import Product
        User = get_user_model()
        seller = User.objects.create_user('media-seller')
        buyer = User.objects.create_user('media-buyer')
        outsider = User.objects.create_user('media-outsider')
        product = Product.objects.create(seller=seller, title='Coat', price=10)
        convo = Conversation.objects.create(buyer=buyer, seller=seller, product=product)
        name = self.save_image('chat/thread-photo.png')
        Message.objects.create(conversation=convo, sender=buyer, kind='image', image=name)
        self.assertEqual(self.client.get('/media/' + name).status_code, 404)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get('/media/' + name).status_code, 404)
        self.client.force_login(buyer)
        response = self.client.get('/media/' + name)
        try:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            list(response.streaming_content)
        finally:
            response.close()
