"""Photo-based refresh for the existing numbered demo catalog."""
import json
from pathlib import Path
from django.conf import settings
from django.core.files import File
from django.db import transaction
from django.utils.text import slugify
from .demo_catalog_v1 import DemoCatalogError


def refresh_demo_catalog(User, Category, Product, ProductImage, username, using='default'):
    rows = json.loads(Path(__file__).with_name('demo_catalog_photos.json').read_text(encoding='utf-8'))
    assets = Path(settings.BASE_DIR) / 'static' / 'images' / 'demo-catalog'
    if len(rows) != 100 or any(not (assets / row['image']).is_file() for row in rows):
        raise DemoCatalogError('The complete 100-photo catalog is required.')
    uploads = []
    updated = 0
    try:
        with transaction.atomic(using=using):
            seller = User._base_manager.using(using).select_for_update().filter(username=username, is_active=True).first()
            if seller is None:
                raise DemoCatalogError('Choose an existing active seller account.')
            for index, row in enumerate(rows, 1):
                slug = f'gaia-demo100-u{seller.pk}-{index:03d}'
                product = Product._base_manager.using(using).select_for_update().filter(slug=slug, seller_id=seller.pk).first()
                if product is None:
                    continue
                title = row['title']
                # Do not overwrite subsequent seller edits; stable IDs stay inside the URL only.
                old_title = product.title.startswith(f'Demo Thrift {index:03d} - ')
                if not old_title and product.title != title:
                    continue
                photos = ProductImage.objects.using(using).filter(product_id=product.pk)
                if not old_title and photos.filter(image__contains='natural-' + row['source_id']).exists():
                    continue
                parent, _ = Category.objects.using(using).get_or_create(slug=slugify(row['department']), defaults={'name': row['department']})
                category, _ = Category.objects.using(using).get_or_create(slug=f'{parent.slug}-{slugify(row["category"])}', defaults={'name': row['category'], 'parent_id': parent.pk})
                image = photos.filter(is_primary=True).first() or photos.first() or ProductImage(product_id=product.pk, is_primary=True)
                with (assets / row['image']).open('rb') as handle:
                    image.image.save('natural-' + row['image'], File(handle), save=False)
                uploads.append((image.image.storage, image.image.name))
                image.save(using=using)
                product.title = title
                product.category_id = category.pk
                product.description = ('DATA CONTOH - bukan penawaran barang nyata. ' + title + '. '
                    'Foto katalog referensi Fashion Product Images (Myntra); hak gambar tetap pada pemiliknya. '
                    'Harga, kondisi, dan ketersediaan hanya simulasi, bukan klaim kondisi barang pada foto.')
                product.style_tags = 'demo,demo100,' + row['colour'].lower() + ',' + row['category'].lower()
                product.save(using=using, update_fields=['title','category','description','style_tags'])
                updated += 1
    except Exception as error:
        for storage, name in uploads:
            try:
                storage.delete(name)
            except Exception:
                pass
        if isinstance(error, DemoCatalogError):
            raise
        raise DemoCatalogError('Photo catalog refresh failed; database changes were rolled back.') from error
    return updated
