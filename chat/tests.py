from django.contrib.auth import get_user_model
from django.test import TestCase
from accounts.models import AccountOrder
from products.models import Product
from . import services
from .models import Conversation, Message

User = get_user_model()


class ChatServiceTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller', password='pw', first_name='Studio Terra')
        self.buyer = User.objects.create_user('buyer', password='pw')
        self.stranger = User.objects.create_user('stranger', password='pw')
        self.product = Product.objects.create(seller=self.seller, title='The Everyday Tote', price=289000)
        self.convo = services.start_conversation(self.buyer, self.product)

    def test_product_chat_is_reused_and_own_listing_is_rejected(self):
        self.assertEqual(services.start_conversation(self.buyer, self.product), self.convo)
        self.assertEqual(self.convo.seller, self.seller)
        with self.assertRaises(services.ChatError):
            services.start_conversation(self.seller, self.product)

    def test_text_message_validation_and_access(self):
        message = services.send_message(self.convo, self.buyer, body='Muat laptop 13 inci?')
        data = services.serialize_message(message, self.buyer)
        self.assertEqual((data['kind'], data['mine'], data['read']), ('text', True, False))
        self.assertFalse(services.serialize_message(message, self.seller)['mine'])
        for sender, body in [(self.buyer, '   '), (self.stranger, 'hai')]:
            with self.subTest(sender=sender.username), self.assertRaises(services.ChatError):
                services.send_message(self.convo, sender, body=body)

    def test_offer_flow(self):
        offer = services.send_message(self.convo, self.buyer, kind=Message.Kind.OFFER, offer_price=250000)
        self.assertEqual(offer.offer_status, Message.OfferStatus.PENDING)
        with self.assertRaises(services.ChatError):
            services.send_message(self.convo, self.seller, kind=Message.Kind.OFFER, offer_price=1)
        with self.assertRaises(services.ChatError):
            services.respond_to_offer(offer, self.buyer, accept=True)
        self.assertEqual(services.respond_to_offer(offer, self.seller, accept=True).offer_status, Message.OfferStatus.ACCEPTED)
        with self.assertRaises(services.ChatError):
            services.respond_to_offer(offer, self.seller, accept=False)

    def test_product_card_message(self):
        message = services.send_message(self.convo, self.seller, kind=Message.Kind.PRODUCT, product=self.product)
        card = services.serialize_message(message, self.buyer)['product']
        self.assertEqual((card['title'], card['price']), ('The Everyday Tote', 289000))
        with self.assertRaises(services.ChatError):
            services.send_message(self.convo, self.seller, kind=Message.Kind.PRODUCT)

    def test_support_chat_with_gaia_care(self):
        support = services.start_support_conversation(self.buyer)
        self.assertEqual(support.kind, Conversation.Kind.SUPPORT)
        self.assertEqual(support.title_for(self.buyer), 'Gaia Care')
        self.assertEqual(services.start_support_conversation(self.buyer), support)
        with self.assertRaises(services.ChatError):
            services.send_message(support, self.buyer, kind=Message.Kind.OFFER, offer_price=1000)

    def test_order_chat_and_system_notice(self):
        order = AccountOrder.objects.create(user=self.buyer, number='GA-2048', date='2026-10-12', status='in_transit', title='The Everyday Tote', subtotal=289000, recipient='Buyer', address='Depok')
        thread = services.start_order_conversation(order)
        self.assertEqual(thread.title_for(self.buyer), 'Order #GA-2048')
        notice = services.send_system_message(thread, '✓ Pesanan GA-2048 telah dikirim')
        data = services.serialize_message(notice, self.buyer)
        self.assertEqual((data['kind'], data['sender'], data['mine']), ('system', None, False))
        with self.assertRaises(services.ChatError):
            services.send_message(thread, self.buyer, kind=Message.Kind.SYSTEM, body='palsu')

    def test_unread_counts_search_and_filter(self):
        services.send_message(self.convo, self.buyer, body='Halo')
        services.send_message(self.convo, self.buyer, body='Masih ada?')
        self.assertEqual(services.unread_count_for(self.seller), 2)
        self.assertEqual(services.conversations_for(self.seller, unread_only=True).get().unread_count, 2)
        self.assertEqual(services.conversations_for(self.seller, search='tote').count(), 1)
        self.assertEqual(services.conversations_for(self.seller, search='denim').count(), 0)
        self.assertEqual(services.mark_read(self.convo, self.seller), 2)
        self.assertEqual(services.unread_count_for(self.seller), 0)
        self.assertFalse(services.conversations_for(self.seller, unread_only=True).exists())

    def test_inbox_newest_first(self):
        support = services.start_support_conversation(self.buyer)
        self.assertEqual(list(services.conversations_for(self.buyer)), [support, self.convo])
        services.send_message(self.convo, self.buyer, body='naik lagi')
        self.assertEqual(list(services.conversations_for(self.buyer)), [self.convo, support])
