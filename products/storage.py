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

    Foto chat dan foto profil tidak ikut: foto chat harus tetap privat.
    """
    if os.environ.get('CLOUDINARY_URL') and not _is_test_run():
        # Di-import di sini karena library-nya langsung error kalau diimpor tanpa kredensial.
        from cloudinary_storage.storage import MediaCloudinaryStorage
        return MediaCloudinaryStorage()
    return default_storage
