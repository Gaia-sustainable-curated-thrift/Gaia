from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from products.demo_catalog_v1 import DemoCatalogError, seed_demo_catalog
from products.models import Category, Product, ProductImage
from products.demo_catalog_v2 import refresh_demo_catalog


class Command(BaseCommand):
    help = 'Add up to 100 repeatable synthetic demo products to an existing seller.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)
        parser.add_argument('--count', type=int, default=100)
        parser.add_argument('--natural-photos', action='store_true', help='Refresh seeded products with distinct catalog photographs.')

    def handle(self, **options):
        try:
            created, kept = seed_demo_catalog(get_user_model(), Category, Product, ProductImage,
                                              options['username'], options['count'])
            if options.get('natural_photos'):
                refresh_demo_catalog(get_user_model(), Category, Product, ProductImage, options['username'])
        except DemoCatalogError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f'Created {created} demo products; kept {kept} existing products for {options["username"]}.'))
