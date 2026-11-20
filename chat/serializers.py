from rest_framework import serializers
from products.models import Product
from . import services
from .models import Conversation, Message


# Ubah URL relatif (/media/..) jadi URL lengkap biar bisa dibuka dari aplikasi mobile
def _absolute(request, url):
    if url and request is not None:
        return request.build_absolute_uri(url)
    return url


# Kartu produk di chat, pakai helper web lalu URL-nya dibikin absolut
def product_card(product, request):
    data = services.serialize_product(product)
    if data:
        data['image'] = _absolute(request, data['image'])
        data['url'] = _absolute(request, data['url'])
    return data


# Satu baris inbox dari sudut pandang user yang login
class ConversationSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    preview = serializers.SerializerMethodField()
    last_at = serializers.SerializerMethodField()
    unread = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ('id', 'kind', 'title', 'initials', 'preview', 'last_at', 'unread', 'product')

    def _viewer(self):
        return self.context['request'].user

    def get_title(self, conversation):
        return conversation.title_for(self._viewer())

    def get_initials(self, conversation):
        return services.initials(conversation.title_for(self._viewer()))

    def get_preview(self, conversation):
        return services.preview_text(conversation.messages.last())

    def get_last_at(self, conversation):
        last = conversation.messages.last()
        return (last.created_at if last else conversation.created_at).isoformat()

    # unread_count cuma ada kalau chat diambil lewat services.conversations_for
    def get_unread(self, conversation):
        return getattr(conversation, 'unread_count', 0)

    def get_product(self, conversation):
        return product_card(conversation.product, self.context.get('request'))


# Satu pesan untuk ditampilkan di ruang chat
class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()
    mine = serializers.SerializerMethodField()
    read = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    product = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            'id', 'kind', 'body', 'image', 'product', 'offer_price',
            'offer_status', 'sender', 'mine', 'created_at', 'read',
        )

    def get_sender(self, message):
        sender = message.sender
        return (sender.get_full_name() or sender.username) if sender else None

    def get_mine(self, message):
        return message.sender_id is not None and message.sender_id == self.context['request'].user.pk

    def get_read(self, message):
        return message.read_at is not None

    def get_image(self, message):
        return _absolute(self.context.get('request'), message.image.url) if message.image else None

    def get_product(self, message):
        return product_card(message.product, self.context.get('request'))


# Data yang dikirim aplikasi saat mengirim pesan. Aturan chat tetap dicek di services.send_message
class MessageCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(
        choices=[k for k in Message.Kind.values if k != Message.Kind.SYSTEM],
        default=Message.Kind.TEXT,
    )
    body = serializers.CharField(max_length=2000, required=False, allow_blank=True, default='')
    image = serializers.ImageField(required=False)
    offer_price = serializers.IntegerField(min_value=1, required=False)
    # id produk untuk pesan kartu produk
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all(), required=False)

    def validate(self, data):
        if data['kind'] == Message.Kind.OFFER and not data.get('offer_price'):
            raise serializers.ValidationError({'offer_price': 'Offer needs a price.'})
        return data
