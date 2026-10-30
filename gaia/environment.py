from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key


def security_settings(environ):
    production = environ.get('PRODUCTION', 'False').lower() == 'true'
    key = environ.get('SECRET_KEY', '').strip()
    if production and (len(key) < 50 or len(set(key)) < 5 or key.startswith('django-insecure-')):
        raise ImproperlyConfigured('Set a new random SECRET_KEY of at least 50 characters in the production environment.')
    return {
        'PRODUCTION': production,
        'SECRET_KEY': key or get_random_secret_key(),
        'DEBUG': not production,
        # PWS must overwrite this header at its trusted HTTPS proxy.
        'SECURE_PROXY_SSL_HEADER': ('HTTP_X_FORWARDED_PROTO', 'https') if production else None,
        'SECURE_SSL_REDIRECT': production,
        'SESSION_COOKIE_SECURE': production,
        'CSRF_COOKIE_SECURE': production,
        'SECURE_HSTS_SECONDS': 31536000 if production else 0,
        'SECURE_HSTS_INCLUDE_SUBDOMAINS': production,
        'SECURE_CONTENT_TYPE_NOSNIFF': True,
    }
