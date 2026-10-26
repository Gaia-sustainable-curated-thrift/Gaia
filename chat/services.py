"""Chat logic shared by every transport.

Views (JSON API) and the Django Channels consumer both call these functions,
so messages are validated, stored and serialized the same way everywhere.
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.utils import timezone
from .models import Conversation, Message


class ChatError(ValueError):
    """Error whose message is safe to show to the user."""


def get_gaia_care_user():
    """The account that answers support and order chats."""
    username = getattr(settings, 'GAIA_CARE_USERNAME', 'gaiacare')
    user, created = get_user_model().objects.get_or_create(username=username, defaults={'first_name': 'Gaia Care', 'is_staff': True})
    if created:
        user.set_unusable_password()
        user.save(update_fields=['password'])
    return user


def conversations_for(user, search='', unread_only=False):
    """Inbox rows for a user, with unread count. Supports the Search box and the 'Belum dibaca' filter."""
    conversations = (
        Conversation.objects
        .filter(Q(buyer=user) | Q(seller=user))
        .select_related('buyer', 'seller', 'product', 'order')
        .annotate(unread_count=Count(
            'messages',
            filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user),
        ))
        .order_by('-updated_at', '-pk')  # annotate() drops Meta.ordering; newest chat goes on top
    )
    search = search.strip()
    if search:
        conversations = conversations.filter(
            Q(buyer__username__icontains=search) | Q(buyer__first_name__icontains=search)
            | Q(seller__username__icontains=search) | Q(seller__first_name__icontains=search)
            | Q(product__title__icontains=search) | Q(order__number__icontains=search)
        )
    if unread_only:
        conversations = conversations.filter(unread_count__gt=0)
    return conversations


def unread_count_for(user):
    """Total unread messages, for the navbar badge."""
    return (
        Message.objects
        .filter(Q(conversation__buyer=user) | Q(conversation__seller=user), read_at__isnull=True)
        .exclude(sender=user)
        .count()
    )


def start_conversation(buyer, product):
    """'Ask seller' on a product page. Reuses the existing thread if there is one."""
    if product.seller_id == buyer.pk:
        raise ChatError('You cannot start a chat about your own listing.')
    conversation, _ = Conversation.objects.get_or_create(
        kind=Conversation.Kind.PRODUCT, product=product, buyer=buyer,
        defaults={'seller': product.seller},
    )
    return conversation


def start_support_conversation(user):
    """'Start Chat' on the empty inbox: talk to Gaia Care."""
    gaia_care = get_gaia_care_user()
    if user.pk == gaia_care.pk:
        raise ChatError('Gaia Care cannot open a support chat with itself.')
    conversation, _ = Conversation.objects.get_or_create(
        kind=Conversation.Kind.SUPPORT, buyer=user,
        defaults={'seller': gaia_care},
    )
    return conversation


def start_order_conversation(order):
    """Thread for one order (e.g. 'Order #GA-2048'), between the buyer and Gaia Care."""
    conversation, _ = Conversation.objects.get_or_create(
        kind=Conversation.Kind.ORDER, order=order,
        defaults={'buyer': order.user, 'seller': get_gaia_care_user()},
    )
    return conversation


def _save(message):
    try:
        message.full_clean()
    except ValidationError as error:
        raise ChatError(' '.join(error.messages))
    message.save()
    message.conversation.save(update_fields=['updated_at'])  # move the thread to the top of the inbox
    return message


def send_message(conversation, sender, kind=Message.Kind.TEXT, body='', image=None, offer_price=None, product=None):
    """Text, image, offer or product card sent by a participant."""
    if not conversation.has_participant(sender):
        raise ChatError('You are not part of this conversation.')
    if kind == Message.Kind.SYSTEM:
        raise ChatError('System notices cannot be sent by users.')
    if kind == Message.Kind.OFFER:
        if conversation.kind != Conversation.Kind.PRODUCT:
            raise ChatError('Offers can only be made in a product chat.')
        if sender.pk != conversation.buyer_id:
            raise ChatError('Only the buyer can make an offer.')
    return _save(Message(
        conversation=conversation,
        sender=sender,
        kind=kind,
        body=(body or '').strip(),
        image=image or '',
        offer_price=offer_price,
        offer_status=Message.OfferStatus.PENDING if kind == Message.Kind.OFFER else '',
        product=product,
    ))


def send_system_message(conversation, body):
    """Centered notice like '✓ Pesanan GA-2048 telah dikirim'. Called by code, never by users."""
    return _save(Message(conversation=conversation, kind=Message.Kind.SYSTEM, body=(body or '').strip()))


def respond_to_offer(message, seller, accept):
    """Seller accepts or declines a pending offer."""
    if message.kind != Message.Kind.OFFER or message.offer_status != Message.OfferStatus.PENDING:
        raise ChatError('This offer can no longer be answered.')
    if seller.pk != message.conversation.seller_id:
        raise ChatError('Only the seller can answer this offer.')
    message.offer_status = Message.OfferStatus.ACCEPTED if accept else Message.OfferStatus.DECLINED
    message.save(update_fields=['offer_status'])
    return message


def mark_read(conversation, reader):
    """Mark the other side's messages as read (drives the '✓✓ Read' label)."""
    return (
        conversation.messages
        .filter(read_at__isnull=True)
        .exclude(sender=reader)
        .update(read_at=timezone.now())
    )


def serialize_product(product):
    if product is None:
        return None
    image = product.primary_image
    return {
        'id': product.pk,
        'title': product.title,
        'price': product.price,
        'image': image.image.url if image else None,
    }


def serialize_message(message, viewer):
    """JSON shape sent to the browser, by the API and by WebSocket alike."""
    sender = message.sender
    return {
        'id': message.pk,
        'kind': str(message.kind),
        'body': message.body,
        'image': message.image.url if message.image else None,
        'product': serialize_product(message.product),
        'offer_price': message.offer_price,
        'offer_status': message.offer_status or None,
        'sender': (sender.get_full_name() or sender.username) if sender else None,
        'mine': sender is not None and sender.pk == viewer.pk,
        'created_at': message.created_at.isoformat(),
        'read': message.read_at is not None,
    }

def initials(name):
    """2 huruf pertama: 'Gaia Care' -> 'GA', 'Order #GA-2048' -> 'OR' (sesuai Figma)."""
    return name.strip()[:2].upper()



def preview_text(message):
    """Potongan pesan terakhir di baris inbox."""
    if message is None:
        return ''
    return {
        Message.Kind.IMAGE: '📷 Photo',
        Message.Kind.PRODUCT: f'🛍 {message.product.title}' if message.product else '🛍 Product',
        Message.Kind.OFFER: f'Offer Rp{message.offer_price:,}'.replace(',', '.'),
    }.get(message.kind, message.body)


def serialize_conversation(conversation, viewer):
    """Satu baris inbox. Dipakai template inbox, API, dan nanti WebSocket."""
    title = conversation.title_for(viewer)
    last = conversation.messages.last()
    return {
        'id': conversation.pk,
        'kind': str(conversation.kind),
        'title': title,
        'initials': initials(title),
        'preview': preview_text(last),
        'last_at': (last.created_at if last else conversation.created_at).isoformat(),
        'unread': getattr(conversation, 'unread_count', 0),
        'product': serialize_product(conversation.product),
    }

