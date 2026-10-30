from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from .forms import MAX_PHOTO_BYTES, ProductListingForm
from .models import Category, Product


def uploaded_photo(name='photo.png'):
    content = BytesIO()
    Image.new('RGB', (4, 4), 'green').save(content, 'PNG')
    return SimpleUploadedFile(name, content.getvalue(), content_type='image/png')


class ProductListingFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.parent = Category.objects.create(name='Women')
        cls.category = Category.objects.create(name='Tops', parent=cls.parent)

    def data(self, **changes):
        data = {'title': 'Linen Shirt', 'category': self.category.pk, 'condition': 'good', 'price': '125000'}
        data.update(changes)
        return data

    def test_plain_and_formatted_rupiah_are_accepted(self):
        for value, expected in [('125000', 125000), ('125.000', 125000), ('1.250.000', 1250000), (' 5000 ', 5000)]:
            with self.subTest(value=value):
                form = ProductListingForm(self.data(price=value))
                self.assertTrue(form.is_valid(), form.errors)
                self.assertEqual(form.cleaned_data['price'], expected)
                self.assertEqual(form.cleaned_data['photos'], [])

    def test_invalid_prices_are_rejected_instead_of_silently_changed(self):
        for value in ['', '-10.000', 'abc100', '0', '1.00', '12.50', '2147483648', '+100', '1,000']:
            with self.subTest(value=value):
                form = ProductListingForm(self.data(price=value))
                self.assertFalse(form.is_valid())
                self.assertIn('price', form.errors)

    def test_only_existing_child_categories_are_allowed(self):
        for value in ['', 'not-a-number', 999999, self.parent.pk]:
            with self.subTest(category=value):
                form = ProductListingForm(self.data(category=value))
                self.assertFalse(form.is_valid())
                self.assertIn('category', form.errors)

    def test_title_is_required_and_respects_model_max_length(self):
        for value in ['', '   ', 'x' * 201]:
            with self.subTest(title=value):
                form = ProductListingForm(self.data(title=value))
                self.assertFalse(form.is_valid())
                self.assertIn('title', form.errors)

    def test_invalid_condition_is_rejected(self):
        form = ProductListingForm(self.data(condition='made-up'))
        self.assertFalse(form.is_valid())
        self.assertIn('condition', form.errors)

    def test_missing_condition_keeps_the_existing_good_default(self):
        data = self.data()
        data.pop('condition')
        form = ProductListingForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['condition'], Product.Condition.GOOD)

    def test_up_to_five_real_images_are_accepted(self):
        photos = [uploaded_photo(f'photo-{index}.png') for index in range(5)]
        form = ProductListingForm(self.data(), MultiValueDict({'photos': photos}))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(len(form.cleaned_data['photos']), 5)

    def test_six_images_are_rejected(self):
        photos = [uploaded_photo(f'photo-{index}.png') for index in range(6)]
        form = ProductListingForm(self.data(), MultiValueDict({'photos': photos}))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['photos'][0].code, 'too_many_photos')

    def test_file_contents_are_verified_even_with_an_image_extension(self):
        for name, content_type in [('not-image.txt', 'text/plain'), ('fake.png', 'image/png')]:
            with self.subTest(name=name):
                photo = SimpleUploadedFile(name, b'not an image', content_type=content_type)
                form = ProductListingForm(self.data(), MultiValueDict({'photos': [photo]}))
                self.assertFalse(form.is_valid())
                self.assertIn('photos', form.errors)

    def test_a_valid_photo_does_not_hide_an_invalid_photo(self):
        photos = [uploaded_photo(), SimpleUploadedFile('fake.png', b'not an image', content_type='image/png')]
        form = ProductListingForm(self.data(), MultiValueDict({'photos': photos}))
        self.assertFalse(form.is_valid())
        self.assertIn('photos', form.errors)

    def test_oversized_uploads_are_rejected_before_image_processing(self):
        photo = SimpleUploadedFile('large.png', b'x' * (MAX_PHOTO_BYTES + 1), content_type='image/png')
        form = ProductListingForm(self.data(), MultiValueDict({'photos': [photo]}))
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors.as_data()['photos'][0].code, 'photo_too_large')


class ProductListingUploadTests(TestCase):
    def test_valid_photos_are_saved_in_order_with_the_first_as_cover(self):
        seller = get_user_model().objects.create_user('image-seller')
        parent = Category.objects.create(name='Women')
        category = Category.objects.create(name='Tops', parent=parent)
        self.client.force_login(seller)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post(reverse('products:sell'), {
                'title': 'Shirt With Photos', 'category': category.pk, 'price': '150.000',
                'photos': [uploaded_photo('front.png'), uploaded_photo('back.png')],
            })
            product = Product.objects.get(title='Shirt With Photos')
            self.assertRedirects(response, reverse('products:detail', args=[product.slug]))
            photos = list(product.images.all())
            self.assertEqual([photo.order for photo in photos], [0, 1])
            self.assertEqual([photo.is_primary for photo in photos], [True, False])
            self.assertEqual(product.primary_image, photos[0])
            self.assertTrue(all(photo.image.storage.exists(photo.image.name) for photo in photos))
