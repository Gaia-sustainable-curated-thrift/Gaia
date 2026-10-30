from datetime import timedelta
from functools import wraps
import hashlib
import math
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from .models import AccountRateLimit


def consume_bucket(key, limit, seconds):
    now = timezone.now()
    digest = hashlib.sha256(key.encode()).hexdigest()
    with transaction.atomic():
        bucket, _ = AccountRateLimit.objects.get_or_create(
            key=digest, defaults={'expires_at': now + timedelta(seconds=seconds)})
        bucket = AccountRateLimit.objects.select_for_update().get(pk=bucket.pk)
        if bucket.expires_at <= now:
            bucket.count = 0
            bucket.expires_at = now + timedelta(seconds=seconds)
        if bucket.count >= limit:
            return max(1, math.ceil((bucket.expires_at - now).total_seconds()))
        bucket.count += 1
        bucket.save(update_fields=['count', 'expires_at'])
    return 0


def sensitive_rate_limit(scope, identity_limit, ip_limit, seconds):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == 'POST':
                identity = request.POST.get('email' if scope == 'reset' else 'username', '').strip().casefold()
                # Alternate username/email spellings of the same account share a login bucket.
                if scope == 'login' and identity:
                    User = get_user_model()
                    query = {'email__iexact': identity} if '@' in identity else {'username__iexact': identity}
                    pk = User.objects.filter(**query).values_list('pk', flat=True).first()
                    if pk is not None:
                        identity = 'user:' + str(pk)
                ip = request.META.get('REMOTE_ADDR', '')
                retry = consume_bucket(f'{scope}:ip:{ip}', ip_limit, seconds)
                if not retry:
                    retry = consume_bucket(f'{scope}:identity:{identity}', identity_limit, seconds)
                if retry:
                    response = HttpResponse('Too many attempts. Please wait before trying again.', status=429, content_type='text/plain')
                    response['Retry-After'] = str(retry)
                    response['Cache-Control'] = 'no-store'
                    return response
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
