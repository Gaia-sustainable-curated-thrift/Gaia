from django.contrib.auth.decorators import login_required
from django.contrib import messages as flash
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST
from accounts.models import AccountOrder
from products.models import Product
from . import services
from .models import Conversation, Message


def _get_conversation(request, pk):
    conversation = get_object_or_404(Conversation.objects.select_related('buyer', 'seller', 'product', 'order'), pk=pk)
    if not conversation.has_participant(request.user):
        raise Http404
    return conversation


def _inbox_rows(request):
    rows = services.conversations_for(
        request.user,
        search=request.GET.get('q', ''),
        unread_only=request.GET.get('filter') == 'unread',
    )
    return [services.serialize_conversation(c, request.user) for c in rows]


# Halaman

@login_required
def inbox(request):
    return render(request, 'chat/inbox.html', {
        'rows': _inbox_rows(request),
        'has_any': services.conversations_for(request.user).exists(),
        'q': request.GET.get('q', ''),
        'filter': request.GET.get('filter', 'all'),
    })


@login_required
def room(request, pk):
    conversation = _get_conversation(request, pk)
    services.mark_read(conversation, request.user)
    title = conversation.title_for(request.user)
    return render(request, 'chat/room.html', {
        'conversation': conversation,
        'title': title,
        'initials': services.initials(title),
        'product': services.serialize_product(conversation.product),
        'thread': [services.serialize_message(m, request.user) for m in conversation.messages.select_related('sender', 'product')],
        'can_offer': conversation.kind == Conversation.Kind.PRODUCT and request.user.pk == conversation.buyer_id,
    })


# Tombol buka chat

@login_required
@require_POST
def start_product_chat(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    try:
        conversation = services.start_conversation(request.user, product)
    except services.ChatError as error:
        flash.error(request, str(error))
        return redirect('chat:inbox')
    return redirect('chat:room', pk=conversation.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def start_support_chat(request):
    try:
        conversation = services.start_support_conversation(request.user)
    except services.ChatError as error:
        flash.error(request, str(error))
        return redirect('chat:inbox')
    return redirect('chat:room', pk=conversation.pk)


@login_required
@require_http_methods(['GET', 'POST'])
def start_order_chat(request, order_id):
    order = get_object_or_404(AccountOrder, pk=order_id, user=request.user)
    try:
        conversation = services.start_order_conversation(order)
    except services.ChatError as error:
        flash.error(request, str(error))
        return redirect('chat:inbox')
    return redirect('chat:room', pk=conversation.pk)


# API

@login_required
def api_conversations(request):
    return JsonResponse({'conversations': _inbox_rows(request)})


@login_required
@require_http_methods(['GET', 'POST'])
def api_messages(request, pk):
    conversation = _get_conversation(request, pk)

    if request.method == 'GET':
        after = request.GET.get('after', '0')
        new = conversation.messages.filter(pk__gt=int(after) if after.isdigit() else 0).select_related('sender', 'product')
        services.mark_read(conversation, request.user)
        last_read = conversation.messages.filter(sender=request.user, read_at__isnull=False).order_by('-pk').first()
        offers = conversation.messages.filter(kind=Message.Kind.OFFER).select_related('sender', 'product')
        return JsonResponse({
            'messages': [services.serialize_message(m, request.user) for m in new],
            'last_read_id': last_read.pk if last_read else 0,
            'offers': [services.serialize_message(m, request.user) for m in offers],
        })

    # POST: kirim pesan
    kind = request.POST.get('kind', Message.Kind.TEXT)
    product = None
    if kind == Message.Kind.PRODUCT:
        product = Product.objects.filter(pk=request.POST.get('product_id')).first()
    offer_price = request.POST.get('offer_price', '')
    try:
        message = services.send_message(
            conversation, request.user, kind=kind,
            body=request.POST.get('body', ''),
            image=request.FILES.get('image'),
            offer_price=int(offer_price) if offer_price.isdigit() else None,
            product=product,
        )
    except services.ChatError as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'message': services.serialize_message(message, request.user)}, status=201)


@login_required
@require_POST
def api_offer(request, pk, message_id):
    conversation = _get_conversation(request, pk)
    offer = get_object_or_404(conversation.messages, pk=message_id)
    try:
        offer = services.respond_to_offer(offer, request.user, accept=request.POST.get('action') == 'accept')
    except services.ChatError as error:
        return JsonResponse({'error': str(error)}, status=400)
    return JsonResponse({'message': services.serialize_message(offer, request.user)})
