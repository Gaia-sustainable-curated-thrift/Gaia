import re
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Product, ProductImage
from .test_forms import uploaded_photo


class PhotoEditCase(TestCase):
    """Dasar untuk test edit foto: seorang seller dengan satu listing berisi tiga foto."""
    ajax = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user('photo-owner')
        cls.other = get_user_model().objects.create_user('photo-other')
        women = Category.objects.create(name='Women')
        cls.tops = Category.objects.create(name='Tops', parent=women)

    def setUp(self):
        cache.clear()
        self.product = Product.objects.create(seller=self.owner, title='Photo Coat', price=100000, category=self.tops)
        self.cover = self.photo('products/cover.png', order=0, primary=True)
        self.second = self.photo('products/second.png', order=1)
        self.third = self.photo('products/third.png', order=2)
        self.client.force_login(self.owner)

    def photo(self, name, order, primary=False, product=None):
        return ProductImage.objects.create(product=product or self.product, image=name, order=order, is_primary=primary)

    def edit(self, remove=(), photos=None, **extra):
        data = {'title': 'Photo Coat', 'category': self.tops.pk, 'condition': 'good', 'price': '100000'}
        if remove:
            data['remove_photos'] = [photo.pk for photo in remove]
        if photos:
            data['photos'] = photos
        return self.client.post(reverse('products:edit', args=[self.product.slug]), data, **extra)

    def names(self):
        return list(self.product.images.order_by('order').values_list('image', flat=True))


class RemoveSavedPhotosTests(PhotoEditCase):
    def test_removed_photo_is_deleted_and_the_rest_are_kept(self):
        response = self.edit(remove=[self.second])
        self.assertRedirects(response, reverse('products:detail', args=[self.product.slug]))
        self.assertEqual(self.names(), ['products/cover.png', 'products/third.png'])
        self.assertTrue(self.product.images.get(is_primary=True).pk == self.cover.pk)

    def test_removing_the_cover_promotes_the_next_photo(self):
        self.edit(remove=[self.cover])
        self.assertEqual(self.names(), ['products/second.png', 'products/third.png'])
        self.assertEqual(self.product.images.get(is_primary=True).pk, self.second.pk)
        self.assertEqual(self.product.primary_image.pk, self.second.pk)

    def test_every_photo_can_be_removed_even_the_last_one(self):
        response = self.edit(remove=[self.cover, self.second, self.third])
        self.assertRedirects(response, reverse('products:detail', args=[self.product.slug]), fetch_redirect_response=False)
        self.assertEqual(self.product.images.count(), 0)
        self.assertIsNone(Product.objects.get(pk=self.product.pk).primary_image)
        self.assertEqual(self.client.get(reverse('products:detail', args=[self.product.slug])).status_code, 200)

    def test_a_single_photo_can_be_removed(self):
        self.product.images.exclude(pk=self.cover.pk).delete()
        self.edit(remove=[self.cover])
        self.assertEqual(self.product.images.count(), 0)

    def test_all_photos_can_be_replaced_in_one_save(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.edit(remove=[self.cover, self.second, self.third], photos=uploaded_photo('fresh.png'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.product.images.count(), 1)
        only = self.product.images.get()
        self.assertTrue(only.is_primary)
        self.assertIn('fresh', only.image.name)

    def test_removed_photos_free_up_room_under_the_five_photo_limit(self):
        self.photo('products/fourth.png', order=3)
        self.photo('products/fifth.png', order=4)
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            too_many = self.edit(remove=[self.second], photos=[uploaded_photo('a.png'), uploaded_photo('b.png')], **self.ajax)
            self.assertEqual(too_many.status_code, 400)
            self.assertEqual(too_many.json()['errors']['photos'], ['A listing can have maximum 5 photos in total.'])
            self.assertEqual(self.product.images.count(), 5)
            fits = self.edit(remove=[self.second], photos=uploaded_photo('a.png'))
        self.assertEqual(fits.status_code, 302)
        self.assertEqual(self.product.images.count(), 5)
        self.assertFalse(ProductImage.objects.filter(pk=self.second.pk).exists())

    def test_photos_of_another_listing_cannot_be_removed(self):
        stranger = Product.objects.create(seller=self.other, title='Not Yours', price=1000, category=self.tops)
        foreign = self.photo('products/foreign.png', order=0, primary=True, product=stranger)
        response = self.edit(remove=[foreign], **self.ajax)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['remove_photos'], ['Choose valid photos to remove.'])
        self.assertTrue(ProductImage.objects.filter(pk=foreign.pk).exists())
        self.assertEqual(self.product.images.count(), 3)

    def test_other_users_cannot_use_the_edit_form_at_all(self):
        self.client.force_login(self.other)
        self.assertEqual(self.edit(remove=[self.second]).status_code, 404)
        self.assertEqual(self.product.images.count(), 3)

    def test_removed_files_are_deleted_once_the_save_is_committed(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            doomed = ProductImage.objects.create(product=self.product, image=uploaded_photo('doomed.png'), order=3)
            path = Path(doomed.image.path)
            self.assertTrue(path.exists())
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                self.edit(remove=[doomed])
            self.assertEqual(len(callbacks), 1)
            self.assertFalse(path.exists())

    def test_a_file_that_cannot_be_deleted_does_not_break_the_save(self):
        with mock.patch('django.core.files.storage.FileSystemStorage.delete', side_effect=OSError('locked')), \
                self.assertLogs('products.views', 'WARNING') as logs, \
                self.captureOnCommitCallbacks(execute=True):
            response = self.edit(remove=[self.second])
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductImage.objects.filter(pk=self.second.pk).exists())
        self.assertIn('products/second.png', logs.output[0])

    def test_edit_page_offers_a_remove_button_on_every_saved_photo(self):
        response = self.client.get(reverse('products:edit', args=[self.product.slug]))
        self.assertContains(response, 'data-remove-existing', count=3)
        # Cover dulu, lalu sisanya sesuai urutan.
        ids = [int(i) for i in re.findall(r'data-photo-id="(\d+)"', response.content.decode())]
        self.assertEqual(ids, [self.cover.pk, self.second.pk, self.third.pk])
        self.assertContains(response, '<span class="sell-photo__cover">Cover</span>', count=1, html=True)

    def test_new_listing_form_has_no_saved_photos_to_remove(self):
        response = self.client.get(reverse('products:sell'))
        self.assertNotContains(response, 'data-remove-existing')


class ReorderPhotosTests(PhotoEditCase):
    """Foto pertama jadi cover. Urutan dikirim halaman sebagai photo_order setelah foto di-drag."""

    def reorder(self, tokens, remove=(), photos=None, **extra):
        data = {'title': 'Photo Coat', 'category': self.tops.pk, 'condition': 'good', 'price': '100000',
                'photo_order': ','.join(tokens)}
        if remove:
            data['remove_photos'] = [photo.pk for photo in remove]
        if photos:
            data['photos'] = photos
        return self.client.post(reverse('products:edit', args=[self.product.slug]), data, **extra)

    def order(self):
        return [photo.pk for photo in self.product.images.order_by('order')]

    def test_dragging_a_photo_to_the_front_makes_it_the_cover(self):
        response = self.reorder([f'e{self.third.pk}', f'e{self.cover.pk}', f'e{self.second.pk}'])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.order(), [self.third.pk, self.cover.pk, self.second.pk])
        self.assertEqual(self.product.primary_image.pk, self.third.pk)
        self.assertEqual(self.product.images.filter(is_primary=True).count(), 1)

    def test_new_photos_can_be_placed_between_saved_ones(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.reorder(
                [f'e{self.cover.pk}', 'n1', f'e{self.second.pk}', 'n0', f'e{self.third.pk}'],
                photos=[uploaded_photo('first.png'), uploaded_photo('second.png')],
            )
        names = [photo.image.name for photo in self.product.images.order_by('order')]
        self.assertEqual(len(names), 5)
        self.assertEqual(names[0], 'products/cover.png')
        self.assertIn('second', names[1])
        self.assertEqual(names[2], 'products/second.png')
        self.assertIn('first', names[3])
        self.assertEqual(names[4], 'products/third.png')

    def test_a_new_photo_can_become_the_cover(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            self.reorder(['n0', f'e{self.cover.pk}', f'e{self.second.pk}', f'e{self.third.pk}'], photos=uploaded_photo('lead.png'))
        self.assertIn('lead', self.product.primary_image.image.name)
        self.assertEqual(self.product.images.count(), 4)

    def test_removed_photos_are_left_out_of_the_order(self):
        self.reorder([f'e{self.third.pk}', f'e{self.cover.pk}'], remove=[self.second])
        self.assertEqual(self.order(), [self.third.pk, self.cover.pk])
        self.assertEqual(self.product.primary_image.pk, self.third.pk)

    def test_photos_missing_from_the_order_keep_their_old_order_at_the_end(self):
        self.reorder([f'e{self.third.pk}'])
        self.assertEqual(self.order(), [self.third.pk, self.cover.pk, self.second.pk])

    def test_unknown_and_repeated_tokens_are_ignored(self):
        self.reorder([f'e{self.second.pk}', f'e{self.second.pk}', 'e999999', 'n7', f'e{self.cover.pk}'])
        self.assertEqual(self.order(), [self.second.pk, self.cover.pk, self.third.pk])

    def test_a_missing_order_keeps_the_saved_cover(self):
        self.edit()
        self.assertEqual(self.order(), [self.cover.pk, self.second.pk, self.third.pk])
        self.assertEqual(self.product.primary_image.pk, self.cover.pk)

    def test_garbage_order_is_rejected(self):
        response = self.reorder(['e1; DROP TABLE', 'x'], **self.ajax)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['errors']['photo_order'], ['Invalid photo order.'])
        self.assertEqual(self.order(), [self.cover.pk, self.second.pk, self.third.pk])

    def test_new_listing_can_pick_which_new_photo_is_the_cover(self):
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response = self.client.post(reverse('products:sell'), {
                'title': 'Fresh Skirt', 'category': self.tops.pk, 'condition': 'good', 'price': '50000',
                'photos': [uploaded_photo('a.png'), uploaded_photo('b.png')], 'photo_order': 'n1,n0',
            })
        self.assertEqual(response.status_code, 302)
        created = Product.objects.get(title='Fresh Skirt')
        self.assertIn('b', created.primary_image.image.name.split('/')[-1])
        self.assertEqual(created.images.count(), 2)
