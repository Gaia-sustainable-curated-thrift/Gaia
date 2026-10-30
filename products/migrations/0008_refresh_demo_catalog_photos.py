from django.conf import settings
from django.db import migrations
from products.demo_catalog_v2 import refresh_demo_catalog


def refresh_catalog(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    alias = schema_editor.connection.alias
    if not User.objects.using(alias).filter(username='danariqbalabi', is_active=True).exists():
        return
    count = refresh_demo_catalog(User, apps.get_model('products', 'Category'),
                                 apps.get_model('products', 'Product'), apps.get_model('products', 'ProductImage'),
                                 'danariqbalabi', using=alias)
    print(f'Refreshed {count} demo products with distinct photos and natural titles.')


class Migration(migrations.Migration):
    dependencies = [('products', '0007_seed_100_danar_demo_products')]
    operations = [migrations.RunPython(refresh_catalog, migrations.RunPython.noop)]
