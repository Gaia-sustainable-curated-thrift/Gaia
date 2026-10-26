import sys
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.db import migrations


TREE = {
    'Women': ['Tops', 'Bottoms', 'Shoes', 'Bags'],
    'Men': ['Tops', 'Bottoms', 'Shoes', 'Bags'],
}

CATALOG = [
    ('Burberry Trench Coat', 'Women Tops', 300000, 'good', 'available'),
    ('Vintage Denim Jacket', 'Men Tops', 185000, 'excellent', 'available'),
    ('Leather Shoulder Bag', 'Women Bags', 450000, 'excellent', 'available'),
    ('Running Sneakers', 'Men Shoes', 220000, 'signs_of_wear', 'sold'),
]


def seed_catalog(apps, schema_editor):
    if 'test' in sys.argv:
        return

    from django.contrib.auth import get_user_model
    from products.models import Category, Product, ProductImage

    categories = {}
    for parent_name, children in TREE.items():
        parent, _ = Category.objects.get_or_create(name=parent_name, parent=None)
        categories[parent_name] = parent
        for child_name in children:
            child, _ = Category.objects.get_or_create(name=child_name, parent=parent)
            categories[f'{parent_name} {child_name}'] = child

    User = get_user_model()
    seller = User.objects.filter(is_superuser=True).order_by('pk').first()
    if seller is None:
        seller, _ = User.objects.get_or_create(username='gaia_demo')
        seller.is_active = True
        seller.set_unusable_password()
        seller.save()

    sample = Path(settings.BASE_DIR) / 'static' / 'images' / 'reference-coat.png'
    for title, category, price, condition, status in CATALOG:
        product, created = Product.objects.get_or_create(
            seller=seller,
            title=title,
            defaults={
                'price': price,
                'condition': condition,
                'status': status,
                'category': categories[category],
            },
        )
        if created and sample.exists() and not product.images.exists():
            image = ProductImage(product=product, is_primary=True, order=0)
            with sample.open('rb') as handle:
                image.image.save(sample.name, File(handle), save=True)


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_remove_product_brand_remove_product_color_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_catalog, migrations.RunPython.noop),
    ]