import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_static(path):
    """Alamat file static dengan penanda versi: /static/js/gaia.js?v=1761830400.

    Server lokal mengirim file static tanpa aturan cache, jadi browser boleh memakai salinan lama
    berjam-jam. Akibatnya HTML yang baru bisa berpasangan dengan JS/CSS lama (tombol muncul tapi
    nggak ngapa-ngapain). Angka di belakang berubah setiap file diubah, jadi browser otomatis
    mengambil file yang baru. Kalau file-nya tidak ditemukan, yang dikembalikan alamat biasa.
    """
    url = static(path)
    found = finders.find(path)
    if isinstance(found, (list, tuple)):
        found = found[0] if found else None
    if not found:
        return url
    try:
        return f'{url}?v={int(os.path.getmtime(found))}'
    except OSError:
        return url
