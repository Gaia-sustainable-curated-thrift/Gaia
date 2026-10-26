from django.contrib import admin
from .models import Conversation, Message
# Register your models here.

class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    fk_name = 'conversation'


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('kind', 'product', 'order', 'buyer', 'seller', 'updated_at')
    list_filter = ('kind',)
    search_fields = ('product__title', 'order__number', 'buyer__username', 'seller__username')
    inlines = [MessageInline]
