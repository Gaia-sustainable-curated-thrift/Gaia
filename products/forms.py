import re

from django import forms
from django.core.exceptions import ValidationError

from .models import Category, Product


MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 5 * 1024 * 1024


class RupiahPriceField(forms.IntegerField):
    """Accept whole rupiah, with optional dot-separated thousands."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        text = str(value).strip()
        if not re.fullmatch(r'[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+', text):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return super().to_python(text.replace('.', ''))


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class ListingPhotosField(forms.ImageField):
    widget = MultipleImageInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        if len(files) > MAX_PHOTOS:
            raise ValidationError('Select maximum 5 photos.', code='too_many_photos')
        cleaned = []
        for photo in files:
            if photo.size > MAX_PHOTO_BYTES:
                raise ValidationError('Each photo must be 5 MB or smaller.', code='photo_too_large')
            # ImageField verifies the actual image contents with Pillow.
            cleaned.append(super().clean(photo, initial))
        return cleaned


class ProductListingForm(forms.ModelForm):
    price = RupiahPriceField(
        min_value=1,
        max_value=2147483647,
        error_messages={
            'required': 'Enter a price.',
            'invalid': 'Enter a valid price, for example 125000 or 125.000.',
        },
    )
    condition = forms.ChoiceField(
        choices=Product.Condition.choices,
        required=False,
        initial=Product.Condition.GOOD,
        error_messages={'invalid_choice': 'Choose a valid condition.'},
    )
    photos = ListingPhotosField(required=False)

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
        self.fields['category'].required = True
        self.fields['category'].queryset = Category.objects.filter(parent__isnull=False).select_related('parent')

    def clean_condition(self):
        return self.cleaned_data['condition'] or Product.Condition.GOOD

    def clean_photos(self):
        photos = self.cleaned_data['photos']
        if self.instance.pk and photos and self.instance.images.count() + len(photos) > MAX_PHOTOS:
            raise ValidationError('A listing can have maximum 5 photos in total.', code='too_many_photos')
        return photos
