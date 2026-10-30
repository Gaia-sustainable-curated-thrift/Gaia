from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from .demo_catalog_v1 import DemoCatalogError, seed_demo_catalog
from .demo_catalog_v2 import refresh_demo_catalog
from .models import BasketItem, Category, Product, ProductImage


class DemoCatalogForm(forms.Form):
    username = forms.CharField(max_length=150, label='Seller username',
                               help_text='Existing active account that will own the 100 demo products.')
    acknowledge = forms.BooleanField(label='I understand these are synthetic demo products, not real items for sale.')

    def clean_username(self):
        username = self.cleaned_data['username']
        if not get_user_model().objects.filter(username=username, is_active=True).exists():
            raise forms.ValidationError('Choose an existing active seller account.')
        return username


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'price', 'category', 'condition', 'status', 'created_at', 'deleted_at')
    list_filter = ('status', 'condition', 'category', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('title', 'seller__username')
    inlines = [ProductImageInline]
    change_list_template = 'admin/products/product/change_list.html'

    def can_seed_demo(self, request):
        return self.has_add_permission(request) and request.user.has_perms(
            ('products.add_category', 'products.add_productimage'))

    def get_urls(self):
        return [path('seed-demo/', self.admin_site.admin_view(self.seed_demo_view),
                     name='products_product_seed_demo')] + super().get_urls()

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {**(extra_context or {}), 'can_seed_demo': self.can_seed_demo(request)})

    @method_decorator(require_http_methods(['GET', 'POST']))
    def seed_demo_view(self, request):
        if not self.can_seed_demo(request):
            raise PermissionDenied
        form = DemoCatalogForm(request.POST if request.method == 'POST' else None,
                               initial={'username': request.user.username})
        if request.method == 'POST' and form.is_valid():
            try:
                created, kept = seed_demo_catalog(get_user_model(), Category, Product, ProductImage,
                                                  form.cleaned_data['username'])
                refresh_demo_catalog(get_user_model(), Category, Product, ProductImage, form.cleaned_data['username'])
            except DemoCatalogError as error:
                form.add_error(None, str(error))
            else:
                self.message_user(request, f'Created {created} demo products; kept {kept} existing products.', messages.SUCCESS)
                return redirect('admin:products_product_changelist')
        return TemplateResponse(request, 'admin/products/product/seed_demo.html', {
            **self.admin_site.each_context(request), 'title': 'Add 100 Demo Products',
            'opts': self.model._meta, 'form': form,
        })

    def get_queryset(self, request):
        # Admin tetap melihat listing yang dihapus seller (kolom deleted_at terisi).
        return Product.all_objects.select_related('seller', 'category')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'slug')
    list_filter = ('parent',)


admin.site.register(BasketItem)