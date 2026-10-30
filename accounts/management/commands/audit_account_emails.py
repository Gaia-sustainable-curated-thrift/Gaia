from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.functions import Lower, Trim


class Command(BaseCommand):
    help = 'List duplicate email account IDs without changing accounts or displaying email addresses.'

    def handle(self, **options):
        users = get_user_model().objects.annotate(email_key=Lower(Trim('email')))
        groups = (users.exclude(email_key='').values('email_key')
                  .annotate(total=Count('pk')).filter(total__gt=1))
        count = 0
        for group in groups:
            ids = list(users.filter(email_key=group['email_key']).values_list('pk', flat=True))
            self.stdout.write(f'Duplicate group: user IDs {ids}')
            count += 1
        self.stdout.write(f'{count} duplicate email group(s). No accounts changed.')
