"""Avatar filenames and storage cleanup after successful database commits."""
import logging
from pathlib import PurePath
from uuid import uuid4
from django.db import transaction

logger = logging.getLogger(__name__)


def avatar_upload_path(instance, filename):
    suffix = PurePath(filename).suffix.lower()
    return f'avatars/{uuid4().hex}{suffix}'


def schedule_avatar_delete(avatar):
    if not avatar:
        return
    name, storage = avatar.name, avatar.storage

    def cleanup():
        try:
            storage.delete(name)
        except OSError:
            logger.warning('Could not remove an old avatar from storage.', exc_info=True)

    transaction.on_commit(cleanup)
