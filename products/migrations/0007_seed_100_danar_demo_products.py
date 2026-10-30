from django.conf import settings
from django.db import migrations
from products.demo_catalog_v1 import seed_demo_catalog


def seed_danar_catalog(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    username = 'danariqbalabi'
    alias = schema_editor.connection.alias
    if not User.objects.using(alias).filter(username=username, is_active=True).exists():
        print('Demo catalog skipped: danariqbalabi is not an active account. Run seed_demo_products after creating the seller.')
        return
    created, kept = seed_demo_catalog(User, apps.get_model('products', 'Category'),
                                      apps.get_model('products', 'Product'), apps.get_model('products', 'ProductImage'),
                                      username, 100, using=alias)
    print(f'Demo catalog for danariqbalabi: created {created}; kept {kept}.')


class Migration(migrations.Migration):
    dependencies = [('products', '0006_product_soft_delete'), ('accounts', '0006_canonical_email_verification')]
    operations = [migrations.RunPython(seed_danar_catalog, migrations.RunPython.noop)]
