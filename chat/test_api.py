from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from products.models import Product
from . import services
from .models import Conversation, Message

User = get_user_model()


class ChatApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user('seller', password='pw', first_name='Studio Terra')
        self.buyer = User.objects.create_user('buyer', password='pw')
        self.stranger = User.objects.create_user('stranger', password='pw')
        self.product = Product.objects.create(seller=self.seller, title='The Everyday Tote', price=289000)
        self.convo = services.start_conversation(self.buyer, self.product)
        services.send_message(self.convo, self.seller, body='Halo, masih ada kok')

    def test_guest_cannot_access_chat(self):
        self.assertIn(self.client.get('/api/chat/conversations/').status_code, (401, 403))

    def test_inbox_lists_only_own_conversations(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.get('/api/chat/conversations/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        row = response.data[0]
        self.assertEqual((row['title'], row['unread'], row['preview']), ('Studio Terra', 1, 'Halo, masih ada kok'))
        self.assertEqual(row['product']['title'], 'The Everyday Tote')

        self.client.force_authenticate(self.stranger)
        self.assertEqual(self.client.get('/api/chat/conversations/').data, [])
        self.assertEqual(self.client.get(f'/api/chat/conversations/{self.convo.pk}/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/chat/conversations/{self.convo.pk}/messages/').status_code, 404)

    def test_inbox_search_and_unread_filter(self):
        self.client.force_authenticate(self.buyer)
        self.assertEqual(len(self.client.get('/api/chat/conversations/', {'q': 'tote'}).data), 1)
        self.assertEqual(len(self.client.get('/api/chat/conversations/', {'q': 'sepatu'}).data), 0)
        self.assertEqual(len(self.client.get('/api/chat/conversations/', {'filter': 'unread'}).data), 1)

    def test_reading_messages_marks_them_read(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.get(f'/api/chat/conversations/{self.convo.pk}/messages/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([(m['body'], m['mine']) for m in response.data], [('Halo, masih ada kok', False)])
        self.assertEqual(self.client.get('/api/chat/conversations/').data[0]['unread'], 0)
        last_id = response.data[-1]['id']
        self.assertEqual(self.client.get(f'/api/chat/conversations/{self.convo.pk}/messages/', {'after': last_id}).data, [])

    def test_send_text_message(self):
        self.client.force_authenticate(self.buyer)
        response = self.client.post(f'/api/chat/conversations/{self.convo.pk}/messages/', {'body': 'Bisa COD?'}, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual((response.data['kind'], response.data['body'], response.data['mine']), ('text', 'Bisa COD?', True))
        empty = self.client.post(f'/api/chat/conversations/{self.convo.pk}/messages/', {'body': '   '}, format='json')
        self.assertEqual(empty.status_code, 400)

    def test_offer_requires_price_and_system_kind_is_rejected(self):
        self.client.force_authenticate(self.buyer)
        url = f'/api/chat/conversations/{self.convo.pk}/messages/'
        self.assertEqual(self.client.post(url, {'kind': 'offer'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'kind': 'system', 'body': 'x'}, format='json').status_code, 400)
        offer = self.client.post(url, {'kind': 'offer', 'offer_price': 250000}, format='json')
        self.assertEqual(offer.status_code, 201)
        self.assertEqual(offer.data['offer_status'], Message.OfferStatus.PENDING)

    def test_start_product_and_support_chat(self):
        self.client.force_authenticate(self.buyer)
        again = self.client.post('/api/chat/conversations/start/', {'product_id': self.product.pk}, format='json')
        self.assertEqual((again.status_code, again.data['id']), (201, self.convo.pk))

        support = self.client.post('/api/chat/conversations/start/', {}, format='json')
        self.assertEqual(support.status_code, 201)
        self.assertEqual(support.data['kind'], Conversation.Kind.SUPPORT)

        self.client.force_authenticate(self.seller)
        own = self.client.post('/api/chat/conversations/start/', {'product_id': self.product.pk}, format='json')
        self.assertEqual(own.status_code, 400)
