from smtplib import SMTPException
import hashlib
import secrets
import time
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.core import signing
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST, require_http_methods
from allauth.account.models import EmailAddress
from products.models import Product
from .forms import DeleteAccountForm, ProfileForm, RegisterForm
from .models import AccountOrder, Profile, WishlistItem


def account_context(request, title, subtitle, active='profile', **extra):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    verified = profile.email_verified or EmailAddress.objects.filter(user=request.user, email__iexact=request.user.email, verified=True).exists()
    return {'title': title, 'subtitle': subtitle, 'active': active, 'profile': profile, 'email_verified': verified, **extra}


def _visible_wishlist_items(user):
    sold_slugs = Product.objects.filter(status=Product.Status.SOLD).values('slug')
    return user.wishlist_items.filter(removed=False).exclude(product_key__in=sold_slugs)


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
    return render(request, 'accounts/profile.html', account_context(request, 'Profile', 'Your space for a more mindful fashion journey.', order_count=request.user.account_orders.count(), wishlist_count=_visible_wishlist_items(request.user).count()))


@login_required
def edit_profile(request):
    context = account_context(request, 'Edit Profile', 'Update your details for a more personal GAIA experience.')
    details = context['profile']
    form = ProfileForm(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None, instance=request.user, initial={'full_name': request.user.get_full_name(), 'phone': details.phone, 'city': details.city, 'country': details.country})
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
    return render(request, 'accounts/wishlist.html', account_context(request, 'Wishlist', 'Save your favorites and give them a new story.', 'wishlist', items=_visible_wishlist_items(request.user), undo_id=request.session.get('wishlist_undo')))


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


DELETE_SESSION_KEY = 'account_delete_confirmation'
DELETE_LINK_SECONDS = 900


def _deletion_blocked(user):
    return user.account_orders.exclude(status=AccountOrder.Status.COMPLETED).exists()


def _deletion_link_valid(request, token):
    pending = request.session.get(DELETE_SESSION_KEY)
    return bool(
        token and pending
        and pending['user'] == request.user.pk
        and pending['email'] == request.user.email
        and 0 <= time.time() - pending['sent_at'] <= DELETE_LINK_SECONDS
        and secrets.compare_digest(pending['digest'], hashlib.sha256(token.encode()).hexdigest())
    )


@login_required
@require_http_methods(['GET', 'POST'])
def delete_account(request, token=None):
    user = request.user
    has_password = user.has_usable_password()
    link_valid = _deletion_link_valid(request, token) if not has_password else False
    blocked = _deletion_blocked(user)
    form = DeleteAccountForm(request.POST if request.method == 'POST' else None, user=user)
    if request.method == 'POST' and form.is_valid():
        if blocked:
            form.add_error(None, 'Finish your pending orders before deleting your account.')
        elif not has_password and not link_valid:
            form.add_error(None, 'Request a new confirmation email and open its link in this browser.')
        else:
            try:
                with transaction.atomic():
                    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
                    if _deletion_blocked(locked_user):
                        form.add_error(None, 'Finish your pending orders before deleting your account.')
                    else:
                        locked_user.delete()
            except (ProtectedError, RestrictedError):
                form.add_error(None, 'Your account has records that must be retained. Please contact support.')
            else:
                if not form.errors:
                    logout(request)
                    messages.success(request, 'Your account has been permanently deleted. You are now logged out.')
                    return redirect('login')
    context = account_context(
        request, 'Delete Account', 'Review what will be removed before you continue.', 'settings',
        form=form, has_password=has_password, delete_link_valid=link_valid,
        delete_link_invalid=bool(token and not link_valid and not has_password),
        deletion_blocked=blocked, listing_count=user.products.count(),
        saved_count=user.wishlist_items.count(), completed_count=user.account_orders.count(),
        delete_email_sent=bool(request.session.get(DELETE_SESSION_KEY)),
    )
    response = render(request, 'accounts/delete_account.html', context)
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@login_required
@require_POST
def send_delete_confirmation(request):
    context = account_context(request, 'Delete Account', '', 'settings')
    if request.user.has_usable_password():
        return redirect('delete_account')
    if _deletion_blocked(request.user):
        messages.error(request, 'Finish your pending orders before deleting your account.')
    elif not request.user.email or not context['email_verified']:
        messages.error(request, 'A verified email is required. Verify your email before deleting your account.')
    else:
        pending = request.session.get(DELETE_SESSION_KEY)
        if pending and 0 <= time.time() - pending['sent_at'] < 60:
            messages.error(request, 'Please wait one minute before requesting another confirmation email.')
            return redirect('delete_account')
        token = secrets.token_urlsafe(32)
        pending = {
            'user': request.user.pk, 'email': request.user.email,
            'digest': hashlib.sha256(token.encode()).hexdigest(), 'sent_at': time.time(),
        }
        protocol = settings.ACCOUNT_DEFAULT_HTTP_PROTOCOL
        path = reverse('delete_account_confirm', args=[token])
        link = f'{protocol}://{request.get_host()}{path}'
        try:
            sent = send_mail(
                'Confirm deletion of your GAIA account',
                'You requested to delete your GAIA account. Open this link in the same browser where you are logged in. '
                'The link expires in 15 minutes. Opening it does not delete your account; you must confirm on the page.\n\n'
                + link + '\n\nIf you did not request this, ignore this email.',
                settings.DEFAULT_FROM_EMAIL, [request.user.email],
            )
            if not sent:
                raise OSError('Email delivery not accepted')
        except (SMTPException, OSError):
            messages.error(request, 'We could not send your confirmation email. Your account has not been deleted. Please try again.')
        else:
            request.session[DELETE_SESSION_KEY] = pending
            messages.success(request, 'Confirmation email sent. Open the link in this browser within 15 minutes to continue.')
    return redirect('delete_account')
