"""Version 1 demo seed API; keep compatible with migration 0007."""
from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils.text import slugify


class DemoCatalogError(ValueError):
    pass


BASE_CATALOG = [('Sage Embroidered Corset Top',
  'Women',
  'Tops',
  85000,
  'good',
  'Atasan sage dengan detail bordir dan potongan fitted.',
  'cat-tops-women.png',
  'sage,corset,embroidered'),
 ('Charcoal Graphic Zip Hoodie',
  'Men',
  'Tops',
  145000,
  'good',
  'Hoodie charcoal beritsleting dengan motif angka di bagian depan.',
  'cat-tops-men.png',
  'charcoal,hoodie,streetwear'),
 ('Washed Denim Mini Skirt',
  'Women',
  'Bottoms',
  95000,
  'signs_of_wear',
  'Rok mini denim dengan efek washed dan detail kancing depan.',
  'cat-bottoms-women.png',
  'denim,mini skirt,vintage'),
 ('Black Embroidered Denim Shorts',
  'Men',
  'Bottoms',
  125000,
  'good',
  'Celana pendek denim hitam dengan bordir kontras pada bagian depan.',
  'cat-bottoms-men.png',
  'black,denim,shorts'),
 ('Brown Buckle Ankle Boots',
  'Women',
  'Shoes',
  175000,
  'signs_of_wear',
  'Ankle boots cokelat dengan detail buckle dan hak sedang.',
  'cat-shoes-women.png',
  'brown,boots,buckle'),
 ('Black Lace-Up Platform Boots',
  'Men',
  'Shoes',
  225000,
  'good',
  'Boots hitam bertali dengan sol tebal dan detail motif kontras.',
  'cat-shoes-men.png',
  'black,boots,platform'),
 ('Mint Quilted Chain Shoulder Bag',
  'Women',
  'Bags',
  165000,
  'good',
  'Tas bahu mint dengan tekstur quilted dan tali rantai.',
  'cat-bags-women.png',
  'mint,quilted,shoulder bag'),
 ('Grey Graphic Chain Backpack',
  'Men',
  'Bags',
  155000,
  'signs_of_wear',
  'Ransel abu-abu bermotif dengan saku depan dan aksen rantai.',
  'cat-bags-men.png',
  'grey,backpack,streetwear'),
 ('Olive Short-Sleeve Zip Hoodie',
  'Women',
  'Tops',
  75000,
  'good',
  'Hoodie olive berlengan pendek dengan resleting depan.',
  'reference-coat.png',
  'olive,hoodie,casual'),
 ('Sage Corset Top - Second Demo Listing',
  'Women',
  'Tops',
  110000,
  'excellent',
  'Contoh listing kedua untuk model atasan corset sage; menggunakan ilustrasi yang sama.',
  'cat-tops-women.png',
  'sage,corset,fitted')]


def seed_demo_catalog(User, Category, Product, ProductImage, username, count=100, using='default'):
    if not isinstance(count, int) or not 1 <= count <= 100:
        raise DemoCatalogError('Choose a count between 1 and 100.')
    assets = Path(settings.BASE_DIR) / 'static' / 'images'
    missing = sorted({row[6] for row in BASE_CATALOG if not (assets / row[6]).is_file()})
    if missing:
        raise DemoCatalogError('Missing demo illustration assets: ' + ', '.join(missing))
    created_count = 0
    uploaded = []
    try:
        with transaction.atomic(using=using):
            seller = User._base_manager.using(using).select_for_update().filter(username=username, is_active=True).first()
            if seller is None:
                raise DemoCatalogError('Choose an existing active seller account.')
            photos = {}
            for index in range(count):
                title, department, category_name, base_price, condition, description, filename, tags = BASE_CATALOG[index % len(BASE_CATALOG)]
                number = index + 1
                slug = f'gaia-demo100-u{seller.pk}-{number:03d}'
                # Includes soft-deleted listings: reruns must not restore or duplicate them.
                existing = Product._base_manager.using(using).filter(slug=slug).first()
                if existing is not None:
                    if existing.seller_id != seller.pk:
                        raise DemoCatalogError('A demo identifier belongs to another seller; no products were changed.')
                    photo = ProductImage.objects.using(using).filter(product_id=existing.pk).first()
                    if photo and photo.image:
                        photos.setdefault(filename, photo.image.name)
                    continue
                parent, _ = Category.objects.using(using).get_or_create(
                    slug=slugify(department), defaults={'name': department})
                category, _ = Category.objects.using(using).get_or_create(
                    slug=f'{parent.slug}-{slugify(category_name)}',
                    defaults={'name': category_name, 'parent_id': parent.pk})
                product = Product._base_manager.using(using).create(
                    seller_id=seller.pk, slug=slug, title=f'Demo Thrift {number:03d} - {title}',
                    category_id=category.pk, price=base_price + (index // len(BASE_CATALOG)) * 5000,
                    condition=condition, status='available', style_tags='demo,demo100,' + tags,
                    description=('DATA DEMO SINTETIS - bukan penawaran barang nyata. ' + description
                                 + ' Harga dan kondisi hanya contoh. Gambar memakai ilustrasi proyek, bukan foto barang nyata.'),
                )
                image = ProductImage(product_id=product.pk, is_primary=True, order=0)
                if filename not in photos:
                    with (assets / filename).open('rb') as handle:
                        image.image.save('demo100-' + filename, File(handle), save=False)
                    photos[filename] = image.image.name
                    uploaded.append((image.image.storage, image.image.name))
                else:
                    image.image.name = photos[filename]
                image.save(using=using)
                created_count += 1
    except Exception as error:
        for storage, name in uploaded:
            try:
                storage.delete(name)
            except Exception:
                pass
        if isinstance(error, DemoCatalogError):
            raise
        raise DemoCatalogError('Demo catalog could not be saved. Check image storage configuration; database changes were rolled back.') from error
    return created_count, count - created_count
