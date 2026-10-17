from smtplib import SMTPException
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from allauth.account.models import EmailAddress
from .forms import ProfileForm, RegisterForm
from .models import AccountOrder, Profile, WishlistItem


def account_context(request, title, subtitle, active='profile', **extra):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    verified = profile.email_verified or EmailAddress.objects.filter(user=request.user, email__iexact=request.user.email, verified=True).exists()
    return {'title': title, 'subtitle': subtitle, 'active': active, 'profile': profile, 'email_verified': verified, **extra}


def register(request):
    if request.user.is_authenticated:
        return redirect('profile')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save()
            Profile.objects.create(user=user)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        token = signing.dumps({'user': user.pk, 'email': user.email}, salt='gaia-email')
        link = request.build_absolute_uri(reverse('verify_email', args=[token]))
        try:
            send_mail('Verify your GAIA email', f'Welcome to GAIA! Verify your email:\n{link}', settings.DEFAULT_FROM_EMAIL, [user.email])
            request.session['verification_email_sent'] = True
        except (SMTPException, OSError):
            request.session['verification_email_sent'] = False
            messages.error(request, 'Your account was created, but the verification email could not be sent. You can continue to your profile.')
        return redirect('account_created')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def account_created(request):
    return render(request, 'registration/account_created.html', {'verification_email_sent': request.session.get('verification_email_sent', False)})


def verify_email(request, token):
    try:
        payload = signing.loads(token, salt='gaia-email', max_age=86400)
        profile = get_object_or_404(Profile, user_id=payload['user'], user__email=payload['email'])
        profile.email_verified = True
        profile.save(update_fields=['email_verified'])
        messages.success(request, 'Email verified. Your sustainable story starts here.')
    except signing.BadSignature:
        messages.error(request, 'This verification link is invalid or has expired.')
    return redirect('profile')


@login_required
def profile(request):
    return render(request, 'accounts/profile.html', account_context(request, 'Profile', 'Your space for a more mindful fashion journey.', order_count=request.user.account_orders.count(), wishlist_count=request.user.wishlist_items.filter(removed=False).count()))


@login_required
def edit_profile(request):
    context = account_context(request, 'Edit Profile', 'Update your details for a more personal GAIA experience.')
    details = context['profile']
    form = ProfileForm(request.POST or None, instance=request.user, initial={'full_name': request.user.get_full_name(), 'phone': details.phone, 'city': details.city, 'country': details.country})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
        messages.success(request, 'Profile updated successfully. Your account details are saved.')
        return redirect('profile')
    return render(request, 'accounts/edit_profile.html', {**context, 'form': form})


@login_required
def orders(request):
    return render(request, 'accounts/orders.html', account_context(request, 'Orders', "Track your orders and follow each item's journey.", 'orders', orders=request.user.account_orders.all()))


@login_required
def order_detail(request, pk):
    order = get_object_or_404(AccountOrder, pk=pk, user=request.user)
    return render(request, 'accounts/order_detail.html', account_context(request, 'Order Details', f'Details and delivery status for order #{order.number}.', 'orders', order=order))


@login_required
def wishlist(request):
    return render(request, 'accounts/wishlist.html', account_context(request, 'Wishlist', 'Save your favorites and give them a new story.', 'wishlist', items=request.user.wishlist_items.filter(removed=False), undo_id=request.session.get('wishlist_undo')))


@login_required
@require_POST
def wishlist_remove(request, pk):
    item = get_object_or_404(WishlistItem, pk=pk, user=request.user, removed=False)
    item.removed = True
    item.save(update_fields=['removed'])
    request.session['wishlist_undo'] = item.pk
    messages.success(request, 'Item removed from your wishlist.')
    return redirect('wishlist')


@login_required
@require_POST
def wishlist_undo(request):
    pk = request.session.pop('wishlist_undo', None)
    if pk:
        WishlistItem.objects.filter(pk=pk, user=request.user, removed=True).update(removed=False)
        messages.success(request, 'Item restored to your wishlist.')
    return redirect('wishlist')


@login_required
def account_settings(request):
    return render(request, 'accounts/settings.html', account_context(request, 'Account Settings', 'Manage security and access to your GAIA account.', 'settings'))


class ChangePasswordView(PasswordChangeView):
    template_name = 'accounts/change_password.html'
    success_url = reverse_lazy('account_settings')

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **account_context(self.request, 'Change Password', 'Use a unique password to keep your account secure.', 'settings')}

    def form_valid(self, form):
        messages.success(self.request, 'Password updated successfully. Your account is secure.')
        return super().form_valid(form)
