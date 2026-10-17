from django.contrib import admin
from .models import AccountOrder, Profile, WishlistItem

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'city', 'country', 'email_verified']
    search_fields = ['user__username', 'user__email']

@admin.register(AccountOrder)
class AccountOrderAdmin(admin.ModelAdmin):
    list_display = ['number', 'user', 'status', 'date', 'subtotal']
    list_filter = ['status']
    search_fields = ['number', 'user__username']

@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'price', 'removed']
    list_filter = ['removed']
