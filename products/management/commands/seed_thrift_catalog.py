"""Create a small, repeatable demo catalog without replacing existing listings."""
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import Category, Product, ProductImage


# Images are existing category illustrations, not photos of goods offered for sale.
CATALOG = [
    ('Sage Embroidered Corset Top', 'Women', 'Tops', 85000, 'good',
     'Atasan sage dengan detail bordir dan potongan fitted.', 'cat-tops-women.png', 'sage,corset,embroidered'),
    ('Charcoal Graphic Zip Hoodie', 'Men', 'Tops', 145000, 'good',
     'Hoodie charcoal beritsleting dengan motif angka di bagian depan.', 'cat-tops-men.png', 'charcoal,hoodie,streetwear'),
    ('Washed Denim Mini Skirt', 'Women', 'Bottoms', 95000, 'signs_of_wear',
     'Rok mini denim dengan efek washed dan detail kancing depan.', 'cat-bottoms-women.png', 'denim,mini skirt,vintage'),
    ('Black Embroidered Denim Shorts', 'Men', 'Bottoms', 125000, 'good',
     'Celana pendek denim hitam dengan bordir kontras pada bagian depan.', 'cat-bottoms-men.png', 'black,denim,shorts'),
    ('Brown Buckle Ankle Boots', 'Women', 'Shoes', 175000, 'signs_of_wear',
     'Ankle boots cokelat dengan detail buckle dan hak sedang.', 'cat-shoes-women.png', 'brown,boots,buckle'),
    ('Black Lace-Up Platform Boots', 'Men', 'Shoes', 225000, 'good',
     'Boots hitam bertali dengan sol tebal dan detail motif kontras.', 'cat-shoes-men.png', 'black,boots,platform'),
    ('Mint Quilted Chain Shoulder Bag', 'Women', 'Bags', 165000, 'good',
     'Tas bahu mint dengan tekstur quilted dan tali rantai.', 'cat-bags-women.png', 'mint,quilted,shoulder bag'),
    ('Grey Graphic Chain Backpack', 'Men', 'Bags', 155000, 'signs_of_wear',
     'Ransel abu-abu bermotif dengan saku depan dan aksen rantai.', 'cat-bags-men.png', 'grey,backpack,streetwear'),
    ('Olive Short-Sleeve Zip Hoodie', 'Women', 'Tops', 75000, 'good',
     'Hoodie olive berlengan pendek dengan resleting depan.', 'reference-coat.png', 'olive,hoodie,casual'),
    ('Sage Corset Top - Second Demo Listing', 'Women', 'Tops', 110000, 'excellent',
     'Contoh listing kedua untuk model atasan corset sage; menggunakan ilustrasi yang sama.', 'cat-tops-women.png', 'sage,corset,fitted'),
]


class Command(BaseCommand):
    help = 'Add 10 synthetic thrift listings with existing illustration assets; safe to rerun.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Existing seller account for these demo listings.')

    def handle(self, *args, **options):
        seller = get_user_model().objects.filter(username=options['username'], is_active=True).first()
        if seller is None:
            raise CommandError('Choose an existing active seller with --username.')
        assets = Path(settings.BASE_DIR) / 'static' / 'images'
        missing = sorted({row[6] for row in CATALOG if not (assets / row[6]).is_file()})
        if missing:
            raise CommandError('Missing illustration assets: ' + ', '.join(missing))

        created_count = 0
        for title, department, category_name, price, condition, description, filename, tags in CATALOG:
            with transaction.atomic():
                parent, _ = Category.objects.get_or_create(name=department, parent=None)
                category, _ = Category.objects.get_or_create(name=category_name, parent=parent)
                product, created = Product.objects.get_or_create(
                    seller=seller, title=title,
                    defaults={
                        'category': category, 'price': price, 'condition': condition,
                        'status': Product.Status.AVAILABLE,
                        'style_tags': 'demo,' + tags,
                        'description': (
                            'DATA DEMO SINTETIS - bukan penawaran barang nyata. '
                            + description
                            + ' Harga dan kondisi adalah contoh. Gambar memakai aset ilustrasi '
                            'proyek, bukan bukti kepemilikan atau keaslian merek. '
                            'Ukuran dan ketersediaan barang nyata belum diverifikasi.'
                        ),
                    },
                )
                if created:
                    image = ProductImage(product=product, is_primary=True)
                    with (assets / filename).open('rb') as handle:
                        image.image.save(filename, File(handle), save=True)
                    created_count += 1
        self.stdout.write(self.style.SUCCESS(
            f'Created {created_count} demo listings; kept {len(CATALOG) - created_count} existing listings '
            f'for seller {seller.username}.'
        ))
