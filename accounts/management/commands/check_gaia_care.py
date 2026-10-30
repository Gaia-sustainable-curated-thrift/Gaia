from django.core.management.base import BaseCommand, CommandError
from accounts.support_readiness import support_readiness


class Command(BaseCommand):
    help = 'Read-only Gaia Care operator check; prints the environment value for a valid staff candidate.'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Optional existing operator to check; does not change the configured operator.')

    def handle(self, **options):
        status = support_readiness(options.get('username'))
        if not status['ready']:
            raise CommandError(' '.join(status['reasons']))
        self.stdout.write(self.style.SUCCESS('Operator account is eligible for Gaia Care.'))
        self.stdout.write(status['environment_line'])
        if status['candidate']:
            self.stdout.write('Candidate only: set this value in PWS Environs and restart. This command did not change configuration.')
        self.stdout.write('Verify a real sign-in and a two-account support conversation before considering support operational.')
