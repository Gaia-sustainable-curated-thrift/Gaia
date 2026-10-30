

from django.db import models
from django.utils import timezone


class ProductReservation(models.Model):
    product = models.OneToOneField(
        'products.Product',
        on_delete=models.CASCADE,
        related_name='transaction_reservation',
    )

    order = models.OneToOneField(
        'accounts.AccountOrder',
        on_delete=models.CASCADE,
        related_name='product_reservation',
    )

    reserved_at = models.DateTimeField(auto_now_add=True)

    expires_at = models.DateTimeField()

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    def __str__(self):
        return f"Reservation: Product {self.product_id} - Order {self.order_id}"


class TransactionOrderState(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAID = "paid", "Paid"
        IN_TRANSIT = "in_transit", "In Transit"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    order = models.OneToOneField(
        "accounts.AccountOrder",
        on_delete=models.CASCADE,
        related_name="transaction_state",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.order_id} - {self.status}"