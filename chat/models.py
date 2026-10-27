from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from accounts.models import AccountOrder
from products.models import Product


class Conversation(models.Model):
    class Kind(models.TextChoices):
        PRODUCT = 'product', 'Product'
        ORDER = 'order', 'Order'
        SUPPORT = 'support', 'Support'

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PRODUCT)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    order = models.ForeignKey(AccountOrder, on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    buyer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='buyer_conversations')
    # chat order/support: diisi akun Gaia Care
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='seller_conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['product', 'buyer'], condition=Q(kind='product'), name='unique_product_buyer_conversation'),
            models.UniqueConstraint(fields=['order'], condition=Q(kind='order'), name='unique_order_conversation'),
            models.UniqueConstraint(fields=['buyer'], condition=Q(kind='support'), name='unique_support_conversation'),
        ]
        ordering = ['-updated_at', '-pk']

    def clean(self):
        if self.buyer_id and self.buyer_id == self.seller_id:
            raise ValidationError('A conversation needs two different people.')
        if self.kind == self.Kind.ORDER and not self.order_id:
            raise ValidationError('Order conversation needs an order.')

    def has_participant(self, user):
        return user.pk in (self.buyer_id, self.seller_id)

    def other_participant(self, user):
        return self.seller if user.pk == self.buyer_id else self.buyer

    def title_for(self, user):
        if self.kind == self.Kind.ORDER and self.order:
            return f'Order #{self.order.number}'
        other = self.other_participant(user)
        return other.get_full_name() or other.username

    def __str__(self):
        subject = self.product or self.order or 'support'
        return f'[{self.kind}] {self.buyer} - {self.seller} · {subject}'


class Message(models.Model):
    class Kind(models.TextChoices):
        TEXT = 'text', 'Text'
        IMAGE = 'image', 'Image'
        OFFER = 'offer', 'Offer'
        PRODUCT = 'product', 'Product card'
        SYSTEM = 'system', 'System notice'

    class OfferStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        ACCEPTED = 'accepted', 'Accepted'
        DECLINED = 'declined', 'Declined'

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    # kosong untuk pesan sistem
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='chat_messages')
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.TEXT)
    body = models.TextField(max_length=2000, blank=True)
    image = models.ImageField(upload_to='chat/%Y/%m/', blank=True)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name='chat_shares')
    offer_price = models.PositiveIntegerField(null=True, blank=True)
    offer_status = models.CharField(max_length=10, choices=OfferStatus.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at', 'pk']

    def clean(self):
        if self.kind == self.Kind.SYSTEM:
            if self.sender_id:
                raise ValidationError('System notices have no sender.')
        elif not self.sender_id:
            raise ValidationError('Message needs a sender.')
        if self.kind in (self.Kind.TEXT, self.Kind.SYSTEM) and not self.body.strip():
            raise ValidationError('Message cannot be empty.')
        if self.kind == self.Kind.IMAGE and not self.image:
            raise ValidationError('Image message needs an image.')
        if self.kind == self.Kind.OFFER and not self.offer_price:
            raise ValidationError('Offer needs a price.')
        if self.kind == self.Kind.PRODUCT and not self.product_id:
            raise ValidationError('Product card needs a product.')

    def __str__(self):
        return f'{self.sender or "system"} [{self.kind}]: {self.body[:40]}'
