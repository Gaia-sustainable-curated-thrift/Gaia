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

    def test_sold_product_cards_are_hidden_but_text_history_and_messages_remain(self):
        shared = services.send_message(self.convo, self.seller, kind=Message.Kind.PRODUCT, product=self.product)
        self.product.status = Product.Status.SOLD
        self.product.save(update_fields=['status'])
        self.assertIsNone(services.serialize_product(self.product))
        self.assertIsNone(services.serialize_message(shared, self.buyer)['product'])
        self.assertIsNone(services.serialize_conversation(self.convo, self.buyer)['product'])
        message = services.send_message(self.convo, self.buyer, body='Question about my order')
        self.assertEqual(message.body, 'Question about my order')
        self.assertEqual(self.convo.messages.count(), 2)

    def test_sold_listing_rejects_new_offers_and_acceptance_but_can_decline(self):
        offer = services.send_message(self.convo, self.buyer, kind=Message.Kind.OFFER, offer_price=250000)
        self.product.status = Product.Status.SOLD
        self.product.save(update_fields=['status'])
        with self.assertRaisesMessage(services.ChatError, 'no longer available'):
            services.send_message(self.convo, self.buyer, kind=Message.Kind.OFFER, offer_price=200000)
        with self.assertRaisesMessage(services.ChatError, 'no longer available'):
            services.respond_to_offer(offer, self.seller, accept=True)
        offer.refresh_from_db()
        self.assertEqual(offer.offer_status, Message.OfferStatus.PENDING)
        self.assertEqual(services.respond_to_offer(offer, self.seller, accept=False).offer_status, Message.OfferStatus.DECLINED)

    def test_deleted_listing_cannot_receive_new_offers(self):
        self.product.delete()
        self.convo.refresh_from_db()
        with self.assertRaisesMessage(services.ChatError, 'no longer available'):
            services.send_message(self.convo, self.buyer, kind=Message.Kind.OFFER, offer_price=200000)


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

    def test_sold_product_room_has_no_product_link_or_offer_controls(self):
        convo = services.start_conversation(self.buyer, self.product)
        services.send_message(convo, self.buyer, body='Previous message')
        self.product.status = Product.Status.SOLD
        self.product.save(update_fields=['status'])
        response = self.client.get(reverse('chat:room', args=[convo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, reverse('products:detail', args=[self.product.slug]))
        self.assertNotContains(response, 'Buat penawaran')
        self.assertContains(response, 'Previous message')


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


class SupportIdentityTests(TestCase):
    def test_existing_ordinary_account_is_never_promoted_or_used_as_support(self):
        impostor = User.objects.create_user('gaiacare', password='pw')
        buyer = User.objects.create_user('new-buyer')
        with self.assertRaises(services.ChatError):
            services.start_support_conversation(buyer)
        impostor.refresh_from_db()
        self.assertFalse(impostor.is_staff)
        self.assertTrue(impostor.check_password('pw'))
        self.assertFalse(Conversation.objects.exists())

    def test_admin_selected_support_must_be_active_staff(self):
        support = User.objects.create_user('staff-support', is_staff=True)
        with self.settings(GAIA_CARE_USER_ID=support.pk):
            self.assertEqual(services.get_gaia_care_user(), support)
            support.is_active = False
            support.save()
            with self.assertRaises(services.ChatError):
                services.get_gaia_care_user()
        with self.settings(GAIA_CARE_USER_ID='invalid'):
            with self.assertRaises(services.ChatError):
                services.get_gaia_care_user()

    def test_old_hijacked_conversation_is_not_silently_reused(self):
        buyer = User.objects.create_user('new-buyer')
        impostor = User.objects.create_user('old-impostor')
        Conversation.objects.create(kind='support', buyer=buyer, seller=impostor)
        with self.assertRaises(services.ChatError):
            services.start_support_conversation(buyer)


class ChatIntegrationTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('seller', password='pw')
        self.buyer = User.objects.create_user('buyer', password='pw')
        self.product = Product.objects.create(seller=self.seller, title='The Everyday Tote', price=100000)
        self.convo = services.start_conversation(self.buyer, self.product)
        self.client.force_login(self.buyer)

    def accept_offer(self, price):
        offer = services.send_message(self.convo, self.buyer, kind=Message.Kind.OFFER, offer_price=price)
        services.respond_to_offer(offer, self.seller, accept=True)

    def checkout(self):
        self.client.post(reverse('products:bag_add', args=[self.product.slug]))
        self.client.post(reverse('transaction:checkout'), {
            'recipient': 'Buyer', 'phone': '0812', 'address': 'Jl', 'city': 'Depok', 'postal_code': '16424', 'country': 'Indonesia',
        })
        self.client.post(reverse('transaction:payment'), {'payment_method': 'bank_transfer'})
        self.client.post(reverse('transaction:confirmation'))
        return AccountOrder.objects.get(user=self.buyer, product=self.product)

    def test_accepted_offer_sets_checkout_price(self):
        self.accept_offer(80000)
        self.assertEqual(self.checkout().subtotal, 80000)

    def test_declined_and_other_buyers_offers_keep_list_price(self):
        offer = services.send_message(self.convo, self.buyer, kind=Message.Kind.OFFER, offer_price=70000)
        services.respond_to_offer(offer, self.seller, accept=False)
        other = User.objects.create_user('other', password='pw')
        other_offer = services.send_message(services.start_conversation(other, self.product), other, kind=Message.Kind.OFFER, offer_price=60000)
        services.respond_to_offer(other_offer, self.seller, accept=True)
        self.assertEqual(self.checkout().subtotal, 100000)

    def test_offer_above_list_price_never_raises_the_price(self):
        self.accept_offer(150000)
        self.assertEqual(self.checkout().subtotal, 100000)

    def test_soft_deleted_listing_has_no_card_or_new_offers(self):
        self.product.soft_delete()
        convo = Conversation.objects.select_related('product').get(pk=self.convo.pk)
        self.assertIsNone(services.serialize_product(convo.product))
        response = self.client.post(reverse('chat:api_messages', args=[convo.pk]), {'kind': 'offer', 'offer_price': '1000'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.client.get(reverse('chat:room', args=[convo.pk])).status_code, 200)

    def test_order_detail_can_chat_seller_and_seller_sees_sale_in_list_only(self):
        order = self.checkout()
        self.assertContains(self.client.get(reverse('order_detail', args=[order.pk])), reverse('chat:start', args=[self.product.pk]))
        self.client.force_login(self.seller)
        self.assertContains(self.client.get(reverse('orders'), {'scope': 'sales'}), order.number)
        self.assertNotContains(self.client.get(reverse('orders')), order.number)
        self.assertNotContains(self.client.get(reverse('orders'), {'scope': 'sales'}), '0812')
        self.assertEqual(self.client.get(reverse('order_detail', args=[order.pk])).status_code, 404)
