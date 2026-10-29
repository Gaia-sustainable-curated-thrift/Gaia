from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reviews.models import Review


class Command(BaseCommand):
    help = "Add repeatable synthetic reviews for a demo seller; existing reviews stay unchanged."

    def add_arguments(self, parser):
        parser.add_argument("--seller", type=int, required=True, help="Existing seller user ID")
        parser.add_argument("--count", type=int, default=50)

    @transaction.atomic
    def handle(self, *args, **options):
        User = get_user_model()
        seller = User.objects.filter(pk=options["seller"], is_active=True).first()
        if seller is None or not (seller.products.exists() or seller.received_reviews.exists()):
            raise CommandError("Choose an existing seller with a product or received reviews.")
        count = options["count"]
        if not 1 <= count <= 200:
            raise CommandError("--count must be between 1 and 200.")
        experiences = [
            ("Friendly and clear", "The seller answered my questions politely and explained the item's condition."),
            ("Quick to help", "Communication was clear and the seller responded to my questions."),
            ("An honest experience", "The seller described the pre-loved item honestly and kept me informed."),
            ("Patient with questions", "I appreciated the seller's patience while I checked the measurements."),
            ("Room to improve", "The seller was polite, though the response could have been quicker."),
        ]
        created = 0
        for index in range(count):
            username = f"gaia_review_demo_{seller.pk}_{index + 1}"
            buyer, new = User.objects.get_or_create(username=username, defaults={"is_active": False, "first_name": "Demo buyer"})
            if buyer.pk == seller.pk:
                raise CommandError("Demo username is already used by the seller.")
            if not new and (buyer.is_active or buyer.has_usable_password()):
                raise CommandError("Demo username already belongs to an existing account.")
            if new:
                buyer.set_unusable_password()
                buyer.save(update_fields=["password"])
            title, comment = experiences[index % len(experiences)]
            _, added = Review.objects.get_or_create(
                reviewer=buyer, seller=seller, title=f"[Demo] {title} {index + 1}",
                defaults={
                    "rating": [5, 4, 5, 3, 2][index % 5], "comment": comment,
                    "is_anonymous": index % 4 == 0, "is_friendly": index % 5 != 4,
                    "is_responsive": index % 3 == 0, "is_trustworthy": index % 2 == 0,
                },
            )
            created += added
        self.stdout.write(self.style.SUCCESS(f"Created {created} synthetic demo reviews for {seller.username}."))
