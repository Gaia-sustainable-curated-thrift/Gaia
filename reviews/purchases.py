"""Read existing order data; never infer a purchase from a product title."""
from accounts.models import AccountOrder


def eligible_orders(buyer, seller):
    return AccountOrder.objects.filter(
        user=buyer, seller=seller,
        status=AccountOrder.Status.COMPLETED,
        seller_review__isnull=True,
    ).exclude(seller=buyer).order_by('-date', '-pk')
