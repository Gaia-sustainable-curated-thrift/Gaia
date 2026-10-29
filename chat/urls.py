from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Halaman
    path('', views.inbox, name='inbox'),
    path('<int:pk>/', views.room, name='room'),
    # Tombol buka chat
    path('start/<int:product_id>/', views.start_product_chat, name='start'),
    path('support/', views.start_support_chat, name='support'),
    path('order/<int:order_id>/', views.start_order_chat, name='order'),
    # API
    path('api/conversations/', views.api_conversations, name='api_conversations'),
    path('api/<int:pk>/messages/', views.api_messages, name='api_messages'),
    path('api/<int:pk>/offers/<int:message_id>/', views.api_offer, name='api_offer'),
]
