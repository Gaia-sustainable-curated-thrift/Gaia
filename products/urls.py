from django.urls import path
from . import views

app_name = 'products'

urlpatterns = [
    path('', views.home, name='home'),
    path('shop/<slug:gender>/', views.listing, name='listing'),
    path('picked/', views.listing, name='picked'),
    path('search/', views.search, name='search'),
    path('bag/add/<slug:slug>/', views.bag_add, name='bag_add'),
    path('bag/set/<slug:slug>/', views.bag_set, name='bag_set'),
    path('bag/undo/', views.bag_undo, name='bag_undo'),
    path('wishlist/add/<slug:slug>/', views.wish_add, name='wish_add'),
    path('<slug:slug>/', views.detail, name='detail'),
]
