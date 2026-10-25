from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.home, name='home'),
    path('shop/<slug:gender>/', views.listing, name='listing'),
    path('picked/', views.listing, name='picked'),
    path('search/', views.search, name='search'),
    path('<slug:slug>/', views.detail, name='detail'),
]
