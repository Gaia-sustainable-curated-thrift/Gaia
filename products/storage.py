import os

from django.core.files.storage import default_storage


def product_image_storage():
    """Where product photos are saved.

    PWS rebuilds the app on every deploy and wipes the local media folder, so in
    any environment with CLOUDINARY_URL set the photos go to Cloudinary instead.
    Without it (local development, tests) they stay in MEDIA_ROOT as before.
    Chat photos and avatars are untouched: chat photos must stay private.
    """
    if os.environ.get('CLOUDINARY_URL'):
        # Imported lazily: the package refuses to load without credentials.
        from cloudinary_storage.storage import MediaCloudinaryStorage
        return MediaCloudinaryStorage()
    return default_storage
