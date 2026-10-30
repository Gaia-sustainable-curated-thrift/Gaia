import os
import sys

from django.core.files.storage import default_storage


def _is_test_run():
    return 'test' in sys.argv


def product_image_storage():
    """Tempat menyimpan foto produk.

    PWS membangun ulang aplikasi tiap deploy dan folder media/ ikut terhapus, jadi kalau
    CLOUDINARY_URL diisi, foto disimpan di Cloudinary. Kalau kosong (misalnya CI), foto
    tetap disimpan di MEDIA_ROOT seperti biasa.

    Saat menjalankan `manage.py test`, Cloudinary sengaja tidak pernah dipakai walaupun
    CLOUDINARY_URL ada di .env: test nggak boleh upload ke akun asli atau butuh internet.

    Foto chat tidak ikut: foto chat harus tetap privat. Avatar memilih storage terpisah di accounts/avatar_storage.py.
    """
    if os.environ.get('CLOUDINARY_URL') and not _is_test_run():
        return _cloudinary_storage()
    return default_storage


def _cloudinary_storage():
    # Di-import di sini karena library-nya langsung error kalau diimpor tanpa kredensial.
    from cloudinary_storage.storage import MediaCloudinaryStorage

    class ProductPhotoStorage(MediaCloudinaryStorage):
        def delete(self, name):
            # Cloudinary menghapus berdasarkan public_id: pakai awalan "media/" dan tanpa
            # ekstensi. Nama di database bisa berupa 'products/2026/10/foto.jpg' (foto lama)
            # atau 'media/products/2026/10/foto_ab12' (upload baru), jadi diseragamkan dulu.
            return super().delete(os.path.splitext(self._prepend_prefix(name))[0])

    return ProductPhotoStorage()
