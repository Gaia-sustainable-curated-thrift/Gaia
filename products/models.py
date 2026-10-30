from django.conf import settings
from django.db import models
from django.utils.text import slugify

from .storage import product_image_storage


class Category(models.Model):
    """Kategori punya dua tingkat: departemen (Women, Men) dan kategori di dalamnya (Tops, Bottoms, ...).

    Departemen nggak punya parent; listing selalu masuk ke salah satu sub-kategori.
    """
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='children')

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            # "Tops" ada dua (Women dan Men), jadi slug sub-kategori ikut nama parent-nya: women-tops, men-tops.
            base = f'{self.parent.slug}-{self.name}' if self.parent else self.name
            self.slug = slugify(base)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.parent.name} · {self.name}' if self.parent else self.name


class Product(models.Model):
    """Satu listing thrift. Tiap listing itu satu barang fisik, jadi nggak ada stok:
    begitu dibeli, statusnya jadi SOLD dan hilang dari toko."""

    class Condition(models.TextChoices):
        EXCELLENT = 'excellent', 'Excellent'
        GOOD = 'good', 'Good'
        SIGNS_OF_WEAR = 'signs_of_wear', 'Signs of wear'

    class Status(models.TextChoices):
        AVAILABLE = 'available', 'Available'
        SOLD = 'sold', 'Sold'

    seller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    condition = models.CharField(max_length=20, choices=Condition.choices, default=Condition.GOOD)
    style_tags = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at', '-pk']

    def save(self, *args, **kwargs):
        # Slug itu bagian URL yang bisa dibaca (/products/wool-coat/). Judul bisa sama, jadi
        # ditambah angka sampai unik: wool-coat-2, wool-coat-3, dan seterusnya.
        if not self.slug:
            max_length = self._meta.get_field('slug').max_length
            base = slugify(self.title)[:max_length] or 'product'
            self.slug = base
            number = 2
            while type(self).objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                suffix = f'-{number}'
                self.slug = f'{base[:max_length - len(suffix)]}{suffix}'
                number += 1
        super().save(*args, **kwargs)

    @property
    def primary_image(self):
        # Pakai all() supaya foto yang sudah di-prefetch dipakai ulang; kalau di-filter, jadi query baru lagi.
        images = list(self.images.all())
        for image in images:
            if image.is_primary:
                return image
        return images[0] if images else None

    @property
    def is_purchasable(self):
        # Dicek di semua tempat yang bisa membeli, masuk bag, atau masuk wishlist.
        return self.status == self.Status.AVAILABLE

    def __str__(self):
        return self.title


class ProductImage(models.Model):
    """Foto listing. Satu jadi cover (is_primary), sisanya ditampilkan sesuai `order`."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/%Y/%m/', storage=product_image_storage)
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'pk']


class BasketItem(models.Model):
    # Model ini nggak dipakai oleh shopping bag. Bag disimpan di session (lihat cart.py)
    # supaya tamu bisa belanja sebelum login. Model ini dibiarkan untuk admin dan data lama.
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='basket_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='basket_items')
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'product'], name='unique_user_basket_product')]
        ordering = ['-added_at']
