import re

from django import forms
from django.core.exceptions import ValidationError

from .models import Category, Product, ProductImage


MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB per foto
MAX_PRICE = 2147483647  # angka terbesar yang muat di kolom harga


class RupiahPriceField(forms.IntegerField):
    """Harga dalam rupiah bulat. Seller boleh nulis 125000 atau 125.000 (titik sebagai pemisah ribuan)."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        text = str(value).strip()
        # Boleh angka polos, atau dikelompokkan per tiga digit pakai titik: 1.250.000 boleh, 1.25 nggak.
        if not re.fullmatch(r'[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+', text):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return super().to_python(text.replace('.', ''))


class MultipleImageInput(forms.ClearableFileInput):
    # Bawaan Django cuma bisa satu file; ini supaya seller bisa pilih beberapa foto sekaligus.
    allow_multiple_selected = True


class ListingPhotosField(forms.ImageField):
    """Maksimal lima foto, masing-masing harus gambar asli dan paling besar 5 MB. Hasilnya berupa list."""

    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        if len(files) > MAX_PHOTOS:
            raise ValidationError(f'Select maximum {MAX_PHOTOS} photos.', code='too_many_photos')
        cleaned = []
        for photo in files:
            if photo.size > MAX_PHOTO_BYTES:
                raise ValidationError('Each photo must be 5 MB or smaller.', code='photo_too_large')
            # ImageField ngecek isi file pakai Pillow, jadi file .txt/.html yang diganti namanya tetap ditolak.
            cleaned.append(super().clean(photo, initial))
        return cleaned


class ProductListingForm(forms.ModelForm):
    """Form untuk "List an item" dan "Edit listing".

    Seller, slug, dan status sengaja nggak dijadikan field di sini: seller diisi oleh view,
    slug dibuat otomatis oleh model, dan listing yang sudah sold tetap sold. Jadi walaupun
    ada yang ngakalin isi form, ketiganya nggak bisa diubah.
    """

    price = RupiahPriceField(
        min_value=1,
        max_value=MAX_PRICE,
        error_messages={
            'required': 'Enter a price.',
            'invalid': 'Enter a valid price, for example 125000 or 125.000.',
        },
    )
    # Boleh dikosongkan; kalau kosong otomatis jadi "Good" (lihat clean_condition).
    condition = forms.ChoiceField(
        choices=Product.Condition.choices,
        required=False,
        initial=Product.Condition.GOOD,
        error_messages={'invalid_choice': 'Choose a valid condition.'},
    )
    photos = ListingPhotosField(required=False)
    # Id foto lama yang mau dibuang saat disimpan. Pilihannya dibatasi ke foto milik listing ini
    # (lihat __init__), jadi foto listing orang lain nggak bisa dihapus lewat form ini.
    remove_photos = forms.ModelMultipleChoiceField(
        queryset=ProductImage.objects.none(),
        required=False,
        widget=forms.MultipleHiddenInput,
        error_messages={
            'invalid_choice': 'Choose valid photos to remove.',
            'invalid_pk_value': 'Choose valid photos to remove.',
            'invalid_list': 'Choose valid photos to remove.',
        },
    )

    # Urutan akhir foto yang dipertahankan, dikirim oleh halaman setelah foto di-drag. Isinya
    # token dipisah koma: e<id> = foto yang sudah tersimpan, n<k> = foto baru ke-k (urutan upload).
    # Foto pertama jadi cover. Kalau kosong atau ada foto yang tidak disebut, urutan lama dipakai.
    photo_order = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = Product
        fields = ['title', 'category', 'condition', 'price', 'photos']
        error_messages = {
            'title': {'required': 'Listing title is required.'},
            'category': {
                'required': 'Choose a category.',
                'invalid_choice': 'Choose a valid category.',
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Listing wajib masuk sub-kategori seperti "Women · Tops", nggak boleh langsung "Women".
        self.fields['category'].required = True
        self.fields['category'].queryset = Category.objects.filter(parent__isnull=False).select_related('parent')
        if self.instance.pk:
            self.fields['remove_photos'].queryset = self.instance.images.all()

    def clean_condition(self):
        return self.cleaned_data['condition'] or Product.Condition.GOOD

    def clean_photo_order(self):
        tokens = [token for token in self.cleaned_data['photo_order'].split(',') if token]
        if not all(re.fullmatch(r'[en][0-9]{1,9}', token) for token in tokens):
            raise ValidationError('Invalid photo order.', code='invalid_photo_order')
        return tokens

    def clean(self):
        # Waktu edit, yang dicek adalah total foto setelah perubahan: foto lama dikurangi yang
        # dibuang, ditambah foto baru. Makanya dicek di sini, setelah semua field selesai divalidasi.
        # Semua foto boleh dibuang, jadi listing boleh berakhir tanpa foto.
        cleaned = super().clean()
        if self.instance.pk:
            total = (
                self.instance.images.count()
                - len(cleaned.get('remove_photos') or [])
                + len(cleaned.get('photos') or [])
            )
            if total > MAX_PHOTOS:
                self.add_error('photos', ValidationError(
                    f'A listing can have maximum {MAX_PHOTOS} photos in total.', code='too_many_photos',
                ))
        return cleaned
