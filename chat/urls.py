from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    # Halaman
    path('', views.inbox, name='inbox'),
    path('<int:pk>/', views.room, name='room'),
    # Tombol yang membuka chat
    path('start/<int:product_id>/', views.start_product_chat, name='start'),   # "Ask seller"
    path('support/', views.start_support_chat, name='support'),               # "Start Chat"
    # API JSON
    path('api/conversations/', views.api_conversations, name='api_conversations'),
    path('api/<int:pk>/messages/', views.api_messages, name='api_messages'),   # GET daftar, POST kirim
    path('api/<int:pk>/offers/<int:message_id>/', views.api_offer, name='api_offer'),
]
