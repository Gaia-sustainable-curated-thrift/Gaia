from django.conf import settings
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=30, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    email_verified = models.BooleanField(default=False)


class WishlistItem(models.Model):
    """Saved listing snapshot, ready for integration with the listing module."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wishlist_items')
    product_key = models.CharField(max_length=100)
    title = models.CharField(max_length=200)
    condition = models.CharField(max_length=80, blank=True)
    price = models.PositiveIntegerField()
    image = models.CharField(max_length=300, blank=True)
    removed = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'product_key'], name='unique_user_wishlist_product')]


class AccountOrder(models.Model):
    """Read-only order snapshot, pending integration with the marketplace module."""
    class Status(models.TextChoices):
        IN_TRANSIT = 'in_transit', 'In transit'
        COMPLETED = 'completed', 'Completed'
        AWAITING_PAYMENT = 'awaiting_payment', 'Awaiting payment'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='account_orders')
    number = models.CharField(max_length=40, unique=True)
    date = models.DateField()
    status = models.CharField(max_length=30, choices=Status.choices)
    title = models.CharField(max_length=200)
    condition = models.CharField(max_length=80, blank=True)
    image = models.CharField(max_length=300, blank=True)
    subtotal = models.PositiveIntegerField()
    shipping = models.PositiveIntegerField(default=0)
    recipient = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField()
    courier = models.CharField(max_length=80, blank=True)
    tracking_number = models.CharField(max_length=100, blank=True)
    status_note = models.CharField(max_length=300, blank=True)
    payment_method = models.CharField(max_length=80, default='Bank transfer')

    @property
    def total(self):
        return self.subtotal + self.shipping

    class Meta:
        ordering = ['-date', '-pk']
