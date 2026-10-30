from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase
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
