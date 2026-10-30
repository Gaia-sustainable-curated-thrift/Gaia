from django.conf import settings
from django.db import migrations
from django.db.models import Count
from django.db.models.functions import Lower

INDEX = 'gaia_unique_username_ci'


def add_index(apps, schema_editor):
    User = apps.get_model(settings.AUTH_USER_MODEL)
    duplicates = (User.objects.using(schema_editor.connection.alias).annotate(key=Lower('username'))
                  .values('key').annotate(total=Count('pk')).filter(total__gt=1))
    if duplicates.exists():
        raise RuntimeError('Case-insensitive duplicate usernames exist. Resolve their ownership before migration; no accounts were merged or renamed.')
    quote = schema_editor.quote_name
    schema_editor.execute(f"CREATE UNIQUE INDEX {quote(INDEX)} ON {quote(User._meta.db_table)} (LOWER({quote('username')}))")


def remove_index(apps, schema_editor):
    schema_editor.execute(f'DROP INDEX {schema_editor.quote_name(INDEX)}')


class Migration(migrations.Migration):
    dependencies = [('accounts', '0006_canonical_email_verification')]
    operations = [migrations.RunPython(add_index, remove_index)]
