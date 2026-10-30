import os
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from accounts.avatar_storage import PREFIX, PersistentAvatarStorage
from accounts.models import Profile


class Command(BaseCommand):
    help = 'Copy surviving local avatars to Cloudinary without deleting local backups.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, **options):
        if not os.environ.get('CLOUDINARY_URL'):
            raise CommandError('Configure CLOUDINARY_URL before copying avatars.')
        storage = PersistentAvatarStorage()
        copied = missing = 0
        for profile in Profile.objects.exclude(avatar='').iterator():
            old = profile.avatar.name
            if old.startswith(PREFIX):
                continue
            if not default_storage.exists(old):
                missing += 1
                continue
            if not options['dry_run']:
                with default_storage.open(old, 'rb') as handle:
                    new = storage.save(old, handle)
                updated = Profile.objects.filter(pk=profile.pk, avatar=old).update(avatar=new)
                if not updated:
                    storage.delete(new)
                    continue
            copied += 1
        self.stdout.write(f'Copied {copied} avatars; missing local files {missing}. Local backups kept.')
