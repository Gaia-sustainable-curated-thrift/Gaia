from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from products.models import Product
from . import services
from .serializers import ConversationSerializer, MessageCreateSerializer, MessageSerializer


# API chat untuk aplikasi mobile. Semua endpoint wajib login,
# dan user cuma bisa lihat chat yang dia ikuti (chat orang lain jadi 404)
class ConversationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ConversationSerializer
    permission_classes = (permissions.IsAuthenticated,)

    # Inbox user, bisa difilter ?q=kata&filter=unread seperti di web
    def get_queryset(self):
        params = self.request.query_params
        return services.conversations_for(
            self.request.user,
            search=params.get('q', '') if self.action == 'list' else '',
            unread_only=self.action == 'list' and params.get('filter') == 'unread',
        )

    # GET  /api/chat/conversations/<id>/messages/?after=<id>  ambil pesan (buat polling)
    # POST /api/chat/conversations/<id>/messages/            kirim pesan
    @action(detail=True, methods=['get', 'post'])
    def messages(self, request, pk=None):
        conversation = self.get_object()
        context = self.get_serializer_context()

        if request.method == 'GET':
            after = request.query_params.get('after', '0')
            rows = (
                conversation.messages
                .filter(pk__gt=int(after) if after.isdigit() else 0)
                .select_related('sender', 'product')
            )
            # Ambil dulu sebelum ditandai dibaca, biar status read di respons sesuai kondisi sebelumnya
            data = MessageSerializer(rows, many=True, context=context).data
            services.mark_read(conversation, request.user)
            return Response(data)

        payload = MessageCreateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            message = services.send_message(conversation, request.user, **payload.validated_data)
        except services.ChatError as error:
            raise ValidationError({'detail': str(error)})
        return Response(MessageSerializer(message, context=context).data, status=status.HTTP_201_CREATED)

    # POST /api/chat/conversations/start/ {"product_id": 3} buka chat produk,
    # tanpa product_id buka chat Gaia Care. Chat yang udah ada dipakai lagi
    @action(detail=False, methods=['post'])
    def start(self, request):
        product_id = request.data.get('product_id')
        try:
            if product_id:
                product = get_object_or_404(Product, pk=product_id)
                conversation = services.start_conversation(request.user, product)
            else:
                conversation = services.start_support_conversation(request.user)
        except services.ChatError as error:
            raise ValidationError({'detail': str(error)})
        data = ConversationSerializer(conversation, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)
