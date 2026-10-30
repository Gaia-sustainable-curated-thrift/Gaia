"""Serve validated upload images on PWS when no separate media server is available."""
from pathlib import PurePosixPath
import warnings

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import default_storage
from django.db.models import Q
from django.http import FileResponse, Http404
from django.views.decorators.http import require_safe


@require_safe
def uploaded_image(request, name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or '\\' in name or not path.parts:
        raise Http404
    if path.parts[0] not in {'avatars', 'products', 'chat'}:
        raise Http404
    if path.parts[0] == 'chat':
        from chat.models import Message
        if not request.user.is_authenticated or not Message.objects.filter(image=name).filter(
            Q(conversation__buyer=request.user) | Q(conversation__seller=request.user)
        ).exists():
            raise Http404
    handle = None
    try:
        if default_storage.size(name) > 10 * 1024 * 1024:
            raise Http404
        handle = default_storage.open(name, 'rb')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            image = Image.open(handle)
            content_type = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp', 'GIF': 'image/gif'}.get(image.format)
            if content_type is None:
                raise Http404
            image.verify()
        handle.seek(0)
    except (OSError, ValueError, SuspiciousFileOperation, UnidentifiedImageError,
            Image.DecompressionBombWarning, Image.DecompressionBombError, Http404):
        if handle is not None:
            handle.close()
        raise Http404
    response = FileResponse(handle, content_type=content_type, filename=path.name)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    response['Cache-Control'] = 'private, no-store' if path.parts[0] == 'chat' else 'public, max-age=3600'
    return response
