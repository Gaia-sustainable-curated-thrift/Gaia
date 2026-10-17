from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from products.models import Category, Product, ProductImage


class Command(BaseCommand):
    help = 'Seed demo categories and products for local development.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True, help='Seller account to attach demo products to.')

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            seller = User.objects.get(username=options['username'])
        except User.DoesNotExist as exc:
            raise CommandError('Create the seller account first.') from exc

        tree = {
            'Women': ['Tops', 'Bottoms', 'Shoes', 'Bags'],
            'Men': ['Tops', 'Bottoms', 'Shoes', 'Bags'],
        }
        categories = {}
        for parent_name, children in tree.items():
            parent, _ = Category.objects.get_or_create(name=parent_name, parent=None)
            categories[parent_name] = parent
            for child_name in children:
                child, _ = Category.objects.get_or_create(name=child_name, parent=parent)
                categories[f'{parent_name} {child_name}'] = child

        sample = Path(settings.BASE_DIR) / 'static' / 'images' / 'reference-coat.png'
        rows = [
            ('Burberry Trench Coat', 'Women Tops', 300000, 'good', 'available'),
            ('Vintage Denim Jacket', 'Men Tops', 185000, 'excellent', 'available'),
            ('Leather Shoulder Bag', 'Women Bags', 450000, 'excellent', 'available'),
            ('Running Sneakers', 'Men Shoes', 220000, 'signs_of_wear', 'sold'),
        ]
        for title, category, price, condition, status in rows:
            product, created = Product.objects.get_or_create(
                seller=seller, title=title,
                defaults={'price': price, 'condition': condition, 'status': status,
                          'category': categories[category], 'brand': title.split()[0]},
            )
            if created and sample.exists():
                image = ProductImage(product=product, is_primary=True)
                with sample.open('rb') as handle:
                    image.image.save(sample.name, File(handle), save=True)
        self.stdout.write(self.style.SUCCESS('Demo products seeded.'))