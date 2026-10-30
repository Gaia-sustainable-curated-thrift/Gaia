import functools
import time

from django.core.cache import cache
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Product

TOO_MANY_TEXT = "You're doing that too often. Please wait a moment and try again."


def owner_required(queryset=None):
    """Hand the view the listing named by the URL slug, but only to its seller.

    Anyone else gets a 404 rather than a 403, so other users cannot probe which
    listings exist. Put it under @login_required.
    """
    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, slug, *args, **kwargs):
            listings = queryset() if callable(queryset) else Product.objects.all()
            product = listings.filter(slug=slug, seller_id=request.user.pk).first()
            if product is None:
                raise Http404('Listing not found')
            return view(request, product, *args, **kwargs)
        return wrapper
    return decorator


def _client_key(request):
    if request.user.is_authenticated:
        # date_joined keeps the key unique even if a deleted user's id is reused.
        return f'user:{request.user.pk}:{int(request.user.date_joined.timestamp())}'
    if not request.session.session_key:
        request.session.save()
    return f'session:{request.session.session_key}'


def _redirect_target(request):
    for target in (request.POST.get('next'), request.headers.get('Referer')):
        if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
            return target
    return reverse('products:home')


def rate_limit(scope, limit, window):
    """Allow at most `limit` POSTs per `window` seconds for one user (or guest session).

    Uses a fixed window in Django's cache. Over the limit, AJAX callers get a 429
    with a toast and form errors they can show; plain form posts are sent back with
    the same message as a toast.
    """
    def decorator(view):
        @functools.wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method != 'POST':
                return view(request, *args, **kwargs)
            now = time.time()
            key = f'ratelimit:{scope}:{_client_key(request)}:{int(now // window)}'
            cache.add(key, 0, window)
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, window)
                count = 1
            if count <= limit:
                return view(request, *args, **kwargs)

            retry_after = max(1, int(window - now % window))
            toast = {'kind': 'error', 'text': TOO_MANY_TEXT}
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response = JsonResponse({
                    'ok': False,
                    'toast': toast,
                    'errors': {'__all__': [TOO_MANY_TEXT]},
                    'retry_after': retry_after,
                }, status=429)
            else:
                request.session['bag_toast'] = toast
                response = redirect(_redirect_target(request))
            response['Retry-After'] = str(retry_after)
            return response
        return wrapper
    return decorator
