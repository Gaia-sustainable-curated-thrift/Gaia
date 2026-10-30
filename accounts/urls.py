from django.contrib.auth import views as auth
from django.urls import path
from . import views
from .forms import EmailAuthenticationForm

urlpatterns = [
    path('login/', auth.LoginView.as_view(template_name='registration/login.html', authentication_form=EmailAuthenticationForm, redirect_authenticated_user=True), name='login'),
    path('logout/', auth.LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('created/', views.account_created, name='account_created'),
    path('verify/resend/', views.resend_verification, name='resend_verification'),
    path('verify/<str:token>/', views.verify_email, name='verify_email'),
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('products/', views.my_products, name='my_products'),
    path('orders/', views.orders, name='orders'),
    path('orders/<int:pk>/', views.order_detail, name='order_detail'),
    path('wishlist/', views.wishlist, name='wishlist'),
    path('wishlist/<int:pk>/remove/', views.wishlist_remove, name='wishlist_remove'),
    path('wishlist/undo/', views.wishlist_undo, name='wishlist_undo'),
    path('delete/', views.delete_account, name='delete_account'),
    path('delete/email/', views.send_delete_confirmation, name='send_delete_confirmation'),
    path('delete/confirm/<str:token>/', views.delete_account, name='delete_account_confirm'),
    path('settings/', views.account_settings, name='account_settings'),
    path('password/change/', views.ChangePasswordView.as_view(), name='password_change'),
    path('password/reset/', auth.PasswordResetView.as_view(), name='password_reset'),
    path('password/reset/sent/', auth.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/', auth.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password/reset/complete/', auth.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
]
