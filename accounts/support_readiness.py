"""Read-only support diagnostics; never create, promote, or change an account."""
from django.conf import settings
from django.contrib.auth import get_user_model
from allauth.socialaccount.models import SocialAccount


def support_readiness(username=None):
    User = get_user_model()
    configured_id = getattr(settings, 'GAIA_CARE_USER_ID', None)
    fallback = getattr(settings, 'GAIA_CARE_USERNAME', 'gaiacare')
    query = {'username': username} if username else {'pk': configured_id} if configured_id else {'username': fallback}
    try:
        user = User.objects.filter(**query).first()
    except (ValueError, TypeError):
        user = None
    reasons = []
    if user is None:
        reasons.append('The selected support account does not exist.')
    else:
        if not user.is_active:
            reasons.append('The support account is inactive.')
        if not user.is_staff:
            reasons.append('The support account is not staff; no permissions were changed.')
        if not user.has_usable_password() and not SocialAccount.objects.filter(user=user, provider='google').exists():
            reasons.append('The support account has no usable password or linked Google sign-in. An operator cannot sign in.')
    return {
        'ready': not reasons, 'reasons': reasons, 'user': user,
        'uses_explicit_id': bool(configured_id), 'candidate': bool(username),
        'environment_line': f'GAIA_CARE_USER_ID={user.pk}' if user is not None else '',
    }
