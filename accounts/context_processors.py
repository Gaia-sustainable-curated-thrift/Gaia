from django.conf import settings


def social_login(request):
    app = settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('APP', {})
    return {'google_login_enabled': bool(app.get('client_id') and app.get('secret'))}
