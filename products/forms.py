import re

from django import forms
from django.core.exceptions import ValidationError

from .models import Category, Product


MAX_PHOTOS = 5
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB per photo
MAX_PRICE = 2147483647  # largest value the price column can hold


class RupiahPriceField(forms.IntegerField):
    """A whole-rupiah price. Sellers may type 125000 or 125.000 (dots as thousands)."""

    def to_python(self, value):
        if value in self.empty_values:
            return None
        text = str(value).strip()
        # Either plain digits, or groups of three after a dot: 1.250.000 is fine, 1.25 is not.
        if not re.fullmatch(r'[0-9]+|[0-9]{1,3}(?:\.[0-9]{3})+', text):
            raise ValidationError(self.error_messages['invalid'], code='invalid')
        return super().to_python(text.replace('.', ''))


class MultipleImageInput(forms.ClearableFileInput):
    # Django's file input takes one file by default; this lets the seller pick several.
    allow_multiple_selected = True


class ListingPhotosField(forms.ImageField):
    """Up to five photos, each a real image of at most 5 MB. Returns a list."""

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
            # ImageField opens the file with Pillow, so a renamed .txt or .html is rejected.
            cleaned.append(super().clean(photo, initial))
        return cleaned


class ProductListingForm(forms.ModelForm):
    """The "List an item" / "Edit listing" form.

    The seller, slug and status are not fields here on purpose: the view sets the
    seller, the model makes the slug, and a sold listing stays sold, so none of
    them can be changed by tampering with the submitted form.
    """

    price = RupiahPriceField(
        min_value=1,
        max_value=MAX_PRICE,
        error_messages={
            'required': 'Enter a price.',
            'invalid': 'Enter a valid price, for example 125000 or 125.000.',
        },
    )
    # Optional in the form; an empty choice falls back to "Good" (see clean_condition).
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
        # A listing must sit in a sub-category such as "Women · Tops", not in "Women" itself.
        self.fields['category'].required = True
        self.fields['category'].queryset = Category.objects.filter(parent__isnull=False).select_related('parent')

    def clean_condition(self):
        return self.cleaned_data['condition'] or Product.Condition.GOOD

    def clean_photos(self):
        # When editing, new photos are added to the ones already saved, so check the total.
        photos = self.cleaned_data['photos']
        if self.instance.pk and photos and self.instance.images.count() + len(photos) > MAX_PHOTOS:
            raise ValidationError(f'A listing can have maximum {MAX_PHOTOS} photos in total.', code='too_many_photos')
        return photos
