from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from .models import Conversation, Message


# Error chat yang pesannya aman ditampilin ke user
class ChatError(ValueError):
    pass


# Ambil akun Gaia Care dari setting, kalau ga diatur pakai username gaiacare. Harus staff dan aktif
def get_gaia_care_user():
    User = get_user_model()
    support_id = getattr(settings, 'GAIA_CARE_USER_ID', None)
    if support_id:
        try:
            user = User.objects.get(pk=int(support_id))
        except (User.DoesNotExist, ValueError, TypeError):
            raise ChatError('GAIA support is unavailable. Please contact an administrator.')
    else:
        username = getattr(settings, 'GAIA_CARE_USERNAME', 'gaiacare')
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={'first_name': 'Gaia Care', 'is_staff': True, 'password': '!'},
        )
    if not user.is_staff or not user.is_active:
        raise ChatError('GAIA support is unavailable. Please contact an administrator.')
    return user


# Daftar chat milik user + jumlah belum dibaca, termasuk search dan filter inbox
def conversations_for(user, search='', unread_only=False):
    conversations = (
        Conversation.objects
        .filter(Q(buyer=user) | Q(seller=user))
        .select_related('buyer', 'seller', 'product', 'order')
        .annotate(unread_count=Count(
            'messages',
            filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=user),
        ))
        .order_by('-updated_at', '-pk')
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


# Total pesan belum dibaca user, buat badge di navbar
def unread_count_for(user):
    return (
        Message.objects
        .filter(Q(conversation__buyer=user) | Q(conversation__seller=user), read_at__isnull=True)
        .exclude(sender=user)
        .count()
    )


# Tombol Chat di produk: ambil chat yang udah ada atau bikin baru. Ga boleh chat produk sendiri
def start_conversation(buyer, product):
    if product.seller_id == buyer.pk:
        raise ChatError('You cannot start a chat about your own listing.')
    conversation, _ = Conversation.objects.get_or_create(
        kind=Conversation.Kind.PRODUCT, product=product, buyer=buyer,
        defaults={'seller': product.seller},
    )
    return conversation


# Tombol Start Chat dan Contact: buka chat user dengan Gaia Care
def start_support_conversation(user):
    gaia_care = get_gaia_care_user()
    if user.pk == gaia_care.pk:
        raise ChatError('Gaia Care cannot open a support chat with itself.')
    conversation, _ = Conversation.objects.get_or_create(
        kind=Conversation.Kind.SUPPORT, buyer=user,
        defaults={'seller': gaia_care},
    )
    if conversation.seller_id != gaia_care.pk:
        raise ChatError('This support conversation needs administrator review.')
    return conversation


# Buka chat soal satu pesanan, antara pembeli dan Gaia Care
def start_order_conversation(order):
    gaia_care = get_gaia_care_user()
    conversation, _ = Conversation.objects.get_or_create(
        kind=Conversation.Kind.ORDER, order=order,
        defaults={'buyer': order.user, 'seller': gaia_care},
    )
    if conversation.seller_id != gaia_care.pk:
        raise ChatError('This support conversation needs administrator review.')
    return conversation


# Validasi lalu simpan pesan, terus naikin chat ke paling atas inbox
def _save(message):
    try:
        message.full_clean()
    except ValidationError as error:
        raise ChatError(' '.join(error.messages))
    message.save()
    message.conversation.save(update_fields=['updated_at'])
    return message


# Kirim pesan dari user. Dicek dulu peserta chat atau bukan, dan aturan offer
def send_message(conversation, sender, kind=Message.Kind.TEXT, body='', image=None, offer_price=None, product=None):
    if not conversation.has_participant(sender):
        raise ChatError('You are not part of this conversation.')
    if kind == Message.Kind.SYSTEM:
        raise ChatError('System notices cannot be sent by users.')
    if kind == Message.Kind.OFFER:
        if conversation.kind != Conversation.Kind.PRODUCT:
            raise ChatError('Offers can only be made in a product chat.')
        if sender.pk != conversation.buyer_id:
            raise ChatError('Only the buyer can make an offer.')
        if conversation.product is None or not conversation.product.is_purchasable:
            raise ChatError('This listing is no longer available for offers.')
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


# Pesan sistem tanpa pengirim, dipanggil dari kode bukan dari user
def send_system_message(conversation, body):
    return _save(Message(conversation=conversation, kind=Message.Kind.SYSTEM, body=(body or '').strip()))


# Seller terima atau tolak penawaran yang masih pending
def respond_to_offer(message, seller, accept):
    if message.kind != Message.Kind.OFFER or message.offer_status != Message.OfferStatus.PENDING:
        raise ChatError('This offer can no longer be answered.')
    if seller.pk != message.conversation.seller_id:
        raise ChatError('Only the seller can answer this offer.')
    if accept and (message.conversation.product is None or not message.conversation.product.is_purchasable):
        raise ChatError('This listing is no longer available for offers.')
    message.offer_status = Message.OfferStatus.ACCEPTED if accept else Message.OfferStatus.DECLINED
    message.save(update_fields=['offer_status'])
    return message


# Harga offer yang udah diterima seller per produk, dipakai bag dan checkout
def accepted_offer_prices(buyer_id, product_ids):
    offers = Message.objects.filter(
        kind=Message.Kind.OFFER,
        offer_status=Message.OfferStatus.ACCEPTED,
        conversation__kind=Conversation.Kind.PRODUCT,
        conversation__buyer_id=buyer_id,
        conversation__product_id__in=product_ids,
    ).order_by('pk').values_list('conversation__product_id', 'offer_price')
    return dict(offers)


# Tandai pesan dari lawan bicara sudah dibaca, jadi tampil Read
def mark_read(conversation, reader):
    return (
        conversation.messages
        .filter(read_at__isnull=True)
        .exclude(sender=reader)
        .update(read_at=timezone.now())
    )


# Ubah produk jadi dict JSON. Produk yang udah ga dijual jadi None
def serialize_product(product):
    if product is None or not product.is_purchasable:
        return None
    image = product.primary_image
    return {
        'id': product.pk,
        'title': product.title,
        'price': product.price,
        'image': image.image.url if image else None,
        'url': reverse('products:detail', args=[product.slug]),
    }


# Ubah pesan jadi dict JSON buat dikirim ke browser
def serialize_message(message, viewer):
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

# 2 huruf pertama nama, buat avatar
def initials(name):
    return name.strip()[:2].upper()



# Potongan pesan terakhir di baris inbox
def preview_text(message):
    if message is None:
        return ''
    if message.kind == Message.Kind.IMAGE:
        return '📷 Photo'
    if message.kind == Message.Kind.PRODUCT:
        return f'🛍 {message.product.title}' if message.product else '🛍 Product'
    if message.kind == Message.Kind.OFFER:
        return f'Offer Rp{message.offer_price:,}'.replace(',', '.')
    return message.body


# Ubah chat jadi dict JSON, satu baris di inbox
def serialize_conversation(conversation, viewer):
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
