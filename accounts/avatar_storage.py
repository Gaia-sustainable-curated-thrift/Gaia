"""Persistent public avatars; chat storage remains private and unchanged."""
import os
import sys
from django.core.files.storage import Storage, default_storage

PREFIX = 'cloud-avatar/'


class PersistentAvatarStorage(Storage):
    def remote(self):
        from products.storage import _cloudinary_storage
        return _cloudinary_storage()

    def backend(self, name):
        return (self.remote(), name[len(PREFIX):]) if name.startswith(PREFIX) else (default_storage, name)

    def _save(self, name, content):
        return PREFIX + self.remote().save(name, content)

    def _open(self, name, mode='rb'):
        storage, key = self.backend(name)
        return storage.open(key, mode)

    def url(self, name):
        storage, key = self.backend(name)
        return storage.url(key)

    def exists(self, name):
        storage, key = self.backend(name)
        return storage.exists(key)

    def size(self, name):
        storage, key = self.backend(name)
        return storage.size(key)

    def delete(self, name):
        storage, key = self.backend(name)
        return storage.delete(key)

    def path(self, name):
        storage, key = self.backend(name)
        return storage.path(key)


def avatar_storage():
    if os.environ.get('CLOUDINARY_URL') and 'test' not in sys.argv:
        return PersistentAvatarStorage()
    return default_storage
