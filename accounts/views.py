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
from django.db import IntegrityError, transaction
from django.db.models import Count, Q
from django.core.paginator import Paginator
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from allauth.account.models import EmailAddress
from .forms import DeleteAccountForm, ProfileForm, RegisterForm
from .models import AccountOrder, Profile, WishlistItem


def account_context(request, title, subtitle, active='profile', **extra):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    verified = profile.email_verified
    return {'title': title, 'subtitle': subtitle, 'active': active, 'profile': profile, 'email_verified': verified, **extra}


def register(request):
    if request.user.is_authenticated:
        return redirect('profile')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                Profile.objects.create(user=user)
        except IntegrityError:
            if get_user_model().objects.filter(email__iexact=form.cleaned_data['email']).exists():
                form.add_error('email', 'An account with this email already exists. Please log in.')
            elif get_user_model().objects.filter(username__iexact=form.instance.username).exists():
                form.add_error(None, 'This username was just taken. Please submit the form again.')
            else:
                raise
            return render(request, 'registration/register.html', {'form': form})
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        try:
            _send_verification_email(request, user)
            request.session['verification_email_sent'] = True
        except (SMTPException, OSError):
            request.session['verification_email_sent'] = False
            messages.error(request, 'Your account was created, but the verification email could not be sent. You can resend it from Account Settings.')
        return redirect('account_created')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def account_created(request):
    return render(request, 'registration/account_created.html', {'verification_email_sent': request.session.get('verification_email_sent', False)})


def verify_email(request, token):
    try:
        payload = signing.loads(token, salt='gaia-email', max_age=86400)
        with transaction.atomic():
            profile = get_object_or_404(Profile.objects.select_for_update(), user_id=payload['user'], user__email=payload['email'])
            email = profile.user.email.strip().lower()
            address = EmailAddress.objects.filter(user=profile.user, email__iexact=email).first()
            if address is None:
                address = EmailAddress.objects.create(
                    user=profile.user, email=email,
                    primary=not EmailAddress.objects.filter(user=profile.user, primary=True).exists(),
                )
            if not address.set_verified():
                messages.error(request, 'This email belongs to another verified account. Please contact support.')
                return redirect('profile')
        messages.success(request, 'Email verified. Your sustainable story starts here.')
    except (signing.BadSignature, KeyError, TypeError):
        messages.error(request, 'This verification link is invalid or has expired.')
    except IntegrityError:
        messages.error(request, 'This email could not be verified. Please contact support.')
    return redirect('profile')


def _send_verification_email(request, user):
    # Reserve the cooldown in the database, so another browser cannot bypass it.
    with transaction.atomic():
        profile, _ = Profile.objects.get_or_create(user=user)
        profile = Profile.objects.select_for_update().get(pk=profile.pk)
        now = timezone.now()
        if profile.verification_sent_at and (now - profile.verification_sent_at).total_seconds() < 60:
            return False
        profile.verification_sent_at = now
        profile.save(update_fields=['verification_sent_at'])
    token = signing.dumps({'user': user.pk, 'email': user.email}, salt='gaia-email')
    scheme = 'https' if settings.PRODUCTION else request.scheme
    path = reverse('verify_email', args=[token])
    link = f'{scheme}://{request.get_host()}{path}'
    sent = send_mail('Verify your GAIA email', f'Welcome to GAIA! Verify your email:\n{link}', settings.DEFAULT_FROM_EMAIL, [user.email])
    if not sent:
        raise OSError('Email delivery not accepted')
    return True


@login_required
@require_POST
def resend_verification(request):
    context = account_context(request, 'Account Settings', '', 'settings')
    if context['email_verified']:
        messages.info(request, 'Your email is already verified.')
    elif not request.user.email:
        messages.error(request, 'Your account has no email address. Please contact support.')
    else:
        try:
            sent = _send_verification_email(request, request.user)
        except (SMTPException, OSError):
            request.session['verification_email_sent'] = False
            messages.error(request, 'Verification email could not be sent. Please try again after one minute.')
        else:
            if sent:
                request.session['verification_email_sent'] = True
                messages.success(request, 'Verification email sent. Check your inbox; the link is valid for 24 hours.')
            else:
                messages.info(request, 'Please wait one minute before requesting another verification email.')
    return redirect('account_settings')


@login_required
def profile(request):
    return render(request, 'accounts/profile.html', account_context(request, 'Profile', 'Your space for a more mindful fashion journey.', listing_count=request.user.products.count(), order_count=request.user.account_orders.count(), wishlist_count=request.user.wishlist_items.filter(removed=False).count()))


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
    page = Paginator(request.user.account_orders.order_by('-date', '-pk'), 12).get_page(request.GET.get('page'))
    return render(request, 'accounts/orders.html', account_context(request, 'Orders', "Track your orders and follow each item's journey.", 'orders', orders=page.object_list, page_obj=page))


@login_required
def order_detail(request, pk):
    order = get_object_or_404(AccountOrder, pk=pk, user=request.user)
    return render(request, 'accounts/order_detail.html', account_context(request, 'Order Details', f'Details and delivery status for order #{order.number}.', 'orders', order=order))


@login_required
def wishlist(request):
    page = Paginator(request.user.wishlist_items.filter(removed=False).order_by('-pk'), 12).get_page(request.GET.get('page'))
    return render(request, 'accounts/wishlist.html', account_context(request, 'Wishlist', 'Save your favorites and give them a new story.', 'wishlist', items=page.object_list, page_obj=page, undo_id=request.session.get('wishlist_undo')))


def _wishlist_page_redirect(request):
    page = request.POST.get('page', '')
    if page.isdecimal() and 0 < len(page) < 8 and int(page) > 0:
        return redirect(f"{reverse('wishlist')}?page={int(page)}")
    return redirect('wishlist')


@login_required
@require_POST
def wishlist_remove(request, pk):
    item = get_object_or_404(WishlistItem, pk=pk, user=request.user, removed=False)
    item.removed = True
    item.save(update_fields=['removed'])
    request.session['wishlist_undo'] = item.pk
    messages.success(request, 'Item removed from your wishlist.')
    return _wishlist_page_redirect(request)


@login_required
@require_POST
def wishlist_undo(request):
    pk = request.session.pop('wishlist_undo', None)
    if pk:
        WishlistItem.objects.filter(pk=pk, user=request.user, removed=True).update(removed=False)
        messages.success(request, 'Item restored to your wishlist.')
    return _wishlist_page_redirect(request)


@login_required
def account_settings(request):
    from allauth.socialaccount.models import SocialAccount
    google_account = SocialAccount.objects.filter(user=request.user, provider='google').exists()
    return render(request, 'accounts/settings.html', account_context(request, 'Account Settings', 'Manage security and access to your GAIA account.', 'settings', google_account=google_account))


class ChangePasswordView(PasswordChangeView):
    template_name = 'accounts/change_password.html'
    success_url = reverse_lazy('account_settings')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and not request.user.has_usable_password():
            messages.info(request, 'Your account uses external sign-in and does not have a local password to change.')
            return redirect('account_settings')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **account_context(self.request, 'Change Password', 'Use a unique password to keep your account secure.', 'settings')}

    def form_valid(self, form):
        messages.success(self.request, 'Password updated successfully. Your account is secure.')
        return super().form_valid(form)


DELETE_SESSION_KEY = 'account_delete_confirmation'
DELETE_LINK_SECONDS = 900


def _deletion_blocked(user):
    return (user.account_orders.exclude(status=AccountOrder.Status.COMPLETED).exists()
            or user.sales_orders.exclude(status=AccountOrder.Status.COMPLETED).exists())


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
            form.add_error(None, 'Finish your pending orders and sales before deleting your account.')
        elif not has_password and not link_valid:
            form.add_error(None, 'Request a new confirmation email and open its link in this browser.')
        else:
            try:
                with transaction.atomic():
                    locked_user = get_user_model().objects.select_for_update().get(pk=user.pk)
                    if _deletion_blocked(locked_user):
                        form.add_error(None, 'Finish your pending orders and sales before deleting your account.')
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
        messages.error(request, 'Finish your pending orders and sales before deleting your account.')
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


@login_required
@require_http_methods(['GET', 'HEAD'])
def my_products(request):
    listings = request.user.products.select_related('category').prefetch_related('images')
    totals = request.user.products.aggregate(
        total=Count('pk'),
        available=Count('pk', filter=Q(status='available')),
        sold=Count('pk', filter=Q(status='sold')),
    )
    status = request.GET.get('status', '')
    if status not in ('available', 'sold'):
        status = ''
    if status:
        listings = listings.filter(status=status)
    page = Paginator(listings.order_by('-created_at', '-pk'), 12).get_page(request.GET.get('page'))
    return render(request, 'accounts/my_products.html', account_context(
        request, 'My Products', 'Manage your listings and give every piece a new story.',
        'products', page_obj=page, selected_status=status, listing_totals=totals,
    ))
