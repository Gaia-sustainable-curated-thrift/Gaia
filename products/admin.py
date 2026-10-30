from django.contrib import admin
from .models import BasketItem, Category, Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'seller', 'price', 'category', 'condition', 'status', 'created_at', 'deleted_at')
    list_filter = ('status', 'condition', 'category', ('deleted_at', admin.EmptyFieldListFilter))
    search_fields = ('title', 'seller__username')
    inlines = [ProductImageInline]

    def get_queryset(self, request):
        # Admin tetap melihat listing yang dihapus seller (kolom deleted_at terisi).
        return Product.all_objects.select_related('seller', 'category')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'slug')
    list_filter = ('parent',)


admin.site.register(BasketItem)