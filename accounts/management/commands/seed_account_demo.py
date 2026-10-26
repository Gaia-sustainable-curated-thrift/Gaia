from datetime import date
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from accounts.models import AccountOrder, Profile, WishlistItem


class Command(BaseCommand):
    help = 'Populate reference orders and wishlist for an existing local demo account. Does not create credentials.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)

    def handle(self, *args, **options):
        try:
            user = get_user_model().objects.get(username=options['username'])
        except get_user_model().DoesNotExist as exc:
            raise CommandError('Create a local demo account first, then pass its username.') from exc
        Profile.objects.get_or_create(user=user)
        for suffix, status, day, note in [
            ('1026001', 'in_transit', 8, 'Your package is on its way. Estimated arrival: 11–12 October 2026.'),
            ('1025008', 'completed', 2, 'Order received on 5 October 2026. Thank you for shopping with us.'),
            ('1026012', 'awaiting_payment', 10, 'Complete payment by 11 October 2026, 10:00 AM WIB.'),
        ]:
            AccountOrder.objects.get_or_create(number=f'DEMO-{user.pk}-{suffix}', defaults={
                'user': user, 'date': date(2026, 10, day), 'status': status,
                'title': 'Burberry Trench Coat', 'condition': 'Very good condition',
                'image': 'images/reference-coat.png', 'subtotal': 300000, 'shipping': 20000,
                'recipient': user.get_full_name() or user.username, 'phone': '+62 812 3456 7890',
                'address': 'Jl. Melati No. 12, Menteng\nJakarta Pusat, DKI Jakarta 10310',
                'courier': 'JNE Reguler', 'tracking_number': '' if status == 'awaiting_payment' else 'JNE0123456789',
                'status_note': note,
            })
        WishlistItem.objects.get_or_create(user=user, product_key='demo-coat', defaults={
            'title': 'Burberry Trench Coat', 'condition': 'Excellent',
            'price': 300000, 'image': 'images/reference-coat.png',
        })
        self.stdout.write(self.style.SUCCESS('Reference orders and wishlist added to the selected demo account.'))
