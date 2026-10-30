import os
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from products.models import ProductImage


class Command(BaseCommand):
    help = (
        'Unggah foto produk yang masih ada di folder media/ lokal ke Cloudinary. '
        'Nama file di database tidak berubah; foto yang sudah ada di Cloudinary dilewati.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Cuma tampilkan apa yang akan diunggah.')

    def handle(self, *args, **options):
        if not os.environ.get('CLOUDINARY_URL'):
            raise CommandError('Isi CLOUDINARY_URL di .env dulu.')

        # Di-import di sini karena library Cloudinary langsung error kalau tidak ada kredensial.
        import cloudinary.uploader
        from cloudinary_storage.storage import MediaCloudinaryStorage

        storage = MediaCloudinaryStorage()
        uploaded = skipped = 0
        missing = []

        for image in ProductImage.objects.all():
            name = image.image.name
            if storage.exists(name):
                skipped += 1
                continue

            path = Path(settings.MEDIA_ROOT) / name
            if not path.is_file():
                missing.append(name)
                continue

            self.stdout.write(f'{"[dry-run] " if options["dry_run"] else ""}Unggah {name}')
            if not options['dry_run']:
                # public_id dibuat dari nama yang tersimpan di database (tanpa ekstensi), supaya
                # alamat foto yang dihitung dari nama itu sama persis dengan yang diunggah.
                public_id = os.path.splitext(storage._prepend_prefix(name))[0]
                cloudinary.uploader.upload(
                    str(path), public_id=public_id, resource_type='image',
                    overwrite=False, unique_filename=False, use_filename=False, tags=storage.TAG,
                )
                # CDN Cloudinary butuh beberapa detik sebelum foto yang baru diunggah bisa dibuka,
                # jadi dicoba ulang dulu. Kalau masih belum, cuma diberi peringatan (fotonya sudah masuk).
                for _ in range(8):
                    if storage.exists(name):
                        break
                    time.sleep(1)
                else:
                    self.stdout.write(self.style.WARNING(f'  {name} sudah diunggah tapi belum bisa dibuka; cek lagi sebentar.'))
            uploaded += 1

        self.stdout.write(self.style.SUCCESS(
            f'Selesai: {uploaded} diunggah, {skipped} sudah ada di Cloudinary, {len(missing)} tidak ditemukan di media/.'
        ))
        for name in missing:
            self.stdout.write(self.style.WARNING(f'  tidak ada di media/: {name} (unggah ulang lewat halaman Edit)'))
