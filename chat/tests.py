from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
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


class ChatPageTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller', password='pw', first_name='Studio Terra')
        self.buyer = User.objects.create_user('buyer', password='pw')
        self.product = Product.objects.create(seller=self.seller, title='The Everyday Tote', price=289000)
        self.client.force_login(self.buyer)

    def test_empty_inbox_offers_gaia_care(self):
        response = self.client.get(reverse('chat:inbox'))
        self.assertContains(response, 'Belum ada percakapan')
        self.assertContains(response, 'Start Chat')
        response = self.client.post(reverse('chat:support'), follow=True)
        self.assertContains(response, 'Gaia Care')

    def test_inbox_lists_conversations_with_unread_badge(self):
        convo = services.start_conversation(self.buyer, self.product)
        services.send_message(convo, self.seller, body='Masih ada kak')
        response = self.client.get(reverse('chat:inbox'))
        self.assertContains(response, 'KOTAK MASUK')
        self.assertContains(response, 'Studio Terra')
        self.assertContains(response, 'chat-badge')
        self.assertContains(self.client.get(reverse('chat:inbox'), {'q': 'denim'}), 'Tidak ada percakapan yang cocok')

    def test_room_shows_product_card_and_thread(self):
        response = self.client.post(reverse('chat:start', args=[self.product.pk]), follow=True)
        self.assertContains(response, 'The Everyday Tote')
        self.assertContains(response, 'Rp289.000')
        self.assertContains(response, 'Buat penawaran')
        self.assertContains(response, 'id="chat-initial"')

    def test_room_is_private_and_needs_login(self):
        convo = services.start_conversation(self.buyer, self.product)
        self.client.force_login(User.objects.create_user('stranger', password='pw'))
        self.assertEqual(self.client.get(reverse('chat:room', args=[convo.pk])).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('chat:inbox')).status_code, 302)


class ChatEntryPointTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller', password='pw', first_name='Studio Terra')
        self.buyer = User.objects.create_user('buyer', password='pw')
        self.product = Product.objects.create(seller=self.seller, title='The Everyday Tote', price=289000)
        self.client.force_login(self.buyer)

    def test_navbar_icon_shows_unread_badge(self):
        convo = services.start_conversation(self.buyer, self.product)
        services.send_message(convo, self.seller, body='Halo')
        response = self.client.get(reverse('chat:inbox'))
        self.assertContains(response, 'class="icon-button nav-chat"')
        self.assertContains(response, 'Chats, 1 unread')
        self.assertContains(response, 'aria-label="My chats"')  # menu drawer
        self.assertContains(self.client.get(reverse('profile')), 'Messages')  # My Account sidebar

    def test_product_page_chat_button(self):
        url = reverse('products:detail', args=[self.product.slug])
        self.assertContains(self.client.get(url), reverse('chat:start', args=[self.product.pk]))
        self.client.force_login(self.seller)
        self.assertNotContains(self.client.get(url), 'pdp-chat')  # no chat with yourself
        self.client.logout()
        self.assertContains(self.client.get(url), f'{reverse("login")}?next=')

    def test_footer_contact_opens_gaia_care(self):
        response = self.client.get(reverse('chat:support'), follow=True)
        self.assertContains(response, 'Gaia Care')
        self.assertContains(self.client.get(reverse('chat:inbox')), reverse('chat:support'))

    def test_order_chat_only_for_order_owner(self):
        order = AccountOrder.objects.create(user=self.buyer, number='GA-2048', date='2026-10-12', status='in_transit', title='Tote', subtotal=1, recipient='B', address='Depok')
        self.assertContains(self.client.get(reverse('order_detail', args=[order.pk])), reverse('chat:order', args=[order.pk]))
        self.assertContains(self.client.get(reverse('chat:order', args=[order.pk]), follow=True), 'Order #GA-2048')
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(reverse('chat:order', args=[order.pk])).status_code, 404)
