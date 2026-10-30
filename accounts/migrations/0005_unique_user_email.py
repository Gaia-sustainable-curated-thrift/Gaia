from django.conf import settings
from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower, Trim


INDEX = 'gaia_unique_user_email_ci'


def add_email_index(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    users = User.objects.using(schema_editor.connection.alias)
    duplicates = (users.annotate(email_key=Lower(Trim('email')))
                  .exclude(email_key='').values('email_key')
                  .annotate(total=Count('pk')).filter(total__gt=1))
    if duplicates.exists():
        raise RuntimeError('Duplicate account emails exist. Run audit_account_emails and resolve ownership before migrating; no accounts were changed.')
    quote = schema_editor.quote_name
    table = quote(User._meta.db_table)
    email = quote(User._meta.get_field('email').column)
    schema_editor.execute(f"CREATE UNIQUE INDEX {quote(INDEX)} ON {table} (LOWER(TRIM({email}))) WHERE TRIM({email}) <> ''")


def remove_email_index(apps, schema_editor):
    schema_editor.execute(f'DROP INDEX {schema_editor.quote_name(INDEX)}')


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_accountorder_product_accountorder_seller'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]
    operations = [migrations.RunPython(add_email_index, remove_email_index)]
