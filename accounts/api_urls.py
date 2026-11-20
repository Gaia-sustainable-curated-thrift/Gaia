from django.urls import path
from . import api_views as api

urlpatterns = [
    path('register/', api.RegisterView.as_view(), name='api-register'),
    path('login/', api.LoginView.as_view(), name='api-login'),
    path('logout/', api.LogoutView.as_view(), name='api-logout'),
    path('me/', api.MeView.as_view(), name='api-me'),
    path('wishlist/', api.WishlistView.as_view(), name='api-wishlist'),
    path('wishlist/products/<int:pk>/', api.WishlistAddView.as_view(), name='api-wishlist-add'),
    path('wishlist/<int:pk>/', api.WishlistItemView.as_view(), name='api-wishlist-item'),
    path('wishlist/<int:pk>/restore/', api.WishlistRestoreView.as_view(), name='api-wishlist-restore'),
    path('verify/resend/', api.ResendVerificationView.as_view(), name='api-verify-resend'),
    path('password/change/', api.ChangePasswordView.as_view(), name='api-password-change'),
    path('password/reset/', api.ResetPasswordView.as_view(), name='api-password-reset'),
]
