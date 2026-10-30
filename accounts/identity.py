from django.conf import settings


def reserved_username(username):
    reserved = {'gaiacare', getattr(settings, 'GAIA_CARE_USERNAME', 'gaiacare').casefold()}
    return username.casefold() in reserved
