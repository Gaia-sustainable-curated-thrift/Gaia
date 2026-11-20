"""Native mobile API. Tokens never authenticate browser sessions or bypass web CSRF."""
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError, RestrictedError
from django.shortcuts import get_object_or_404
from rest_framework.authentication import TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product
from .forms import DeleteAccountForm, EmailAuthenticationForm, ProfileForm, RegisterForm
from .models import Profile, WishlistItem
from .throttling import consume_bucket
from .views import _deletion_blocked, _send_verification_email, _visible_wishlist_items


def check_rate(request, scope, identity, identity_limit, ip_limit, seconds):
    retry = consume_bucket(f'{scope}:ip:{request.META.get("REMOTE_ADDR", "")}', ip_limit, seconds)
    if not retry:
        retry = consume_bucket(f'{scope}:identity:{identity}', identity_limit, seconds)
    if retry:
        raise Throttled(wait=retry)


def valid(form):
    if not form.is_valid():
        raise ValidationError(dict(form.errors))
    return form


def user_data(request, user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return {
        'id': user.pk, 'full_name': user.get_full_name(), 'username': user.username,
        'email': user.email, 'phone': profile.phone, 'city': profile.city,
        'country': profile.country, 'email_verified': profile.email_verified,
        'has_password': user.has_usable_password(),
        'avatar_url': request.build_absolute_uri(profile.avatar.url) if profile.avatar else None,
    }


def wishlist_data(request, item):
    return {
        'id': item.pk, 'product_key': item.product_key, 'title': item.title,
        'condition': item.condition, 'price': item.price,
        'image_url': request.build_absolute_uri(item.image) if item.image else None,
    }


class AccountAPIView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class PublicAPIView(AccountAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]


class RegisterView(PublicAPIView):
    def post(self, request):
        check_rate(request, 'api-register', '', 10, 10, 3600)
        form = valid(RegisterForm(request.data))
        try:
            with transaction.atomic():
                user = form.save()
                Profile.objects.get_or_create(user=user)
                token = Token.objects.create(user=user)
        except IntegrityError:
            raise ValidationError({'detail': 'Email or username already exists. Please try again.'})
        warning = None
        try:
            _send_verification_email(request, user)
        except (SMTPException, OSError):
            warning = 'Account created, but verification email could not be sent. Please resend from settings.'
        return Response({'token': token.key, 'user': user_data(request, user), 'warning': warning}, status=201)


class LoginView(PublicAPIView):
    def post(self, request):
        identifier = str(request.data.get('username', '')).strip().casefold()
        query = {'email__iexact': identifier} if '@' in identifier else {'username__iexact': identifier}
        pk = get_user_model().objects.filter(**query).values_list('pk', flat=True).first()
        check_rate(request, 'login', f'user:{pk}' if pk is not None else identifier, 10, 60, 600)
        form = valid(EmailAuthenticationForm(request=request, data=request.data))
        user = form.get_user()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': user_data(request, user)})


class LogoutView(AccountAPIView):
    def post(self, request):
        request.auth.delete()
        return Response(status=204)


class MeView(AccountAPIView):
    def get(self, request):
        return Response(user_data(request, request.user))

    def patch(self, request):
        user = request.user
        # ProfileForm remains the single authority for web and mobile validation.
        fields = user_data(request, user)
        fields.update({k: request.data[k] for k in ('full_name', 'username', 'phone', 'city', 'country') if k in request.data})
        form = valid(ProfileForm(fields, request.FILES, instance=user))
        try:
            with transaction.atomic():
                form.save()
        except IntegrityError:
            raise ValidationError({'username': ['This username is already taken.']})
        return Response(user_data(request, user))

    def delete(self, request):
        if not request.user.has_usable_password():
            raise ValidationError({'detail': 'Use the web email confirmation flow to delete an external sign-in account.'})
        valid(DeleteAccountForm(request.data, user=request.user))
        try:
            with transaction.atomic():
                user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
                if _deletion_blocked(user):
                    raise ValidationError({'detail': 'Finish pending purchases and sales before deleting your account.'})
                user.delete()
        except (ProtectedError, RestrictedError):
            raise ValidationError({'detail': 'Account records must be retained. Please contact support.'})
        return Response(status=204)


class WishlistPagination(PageNumberPagination):
    page_size = 12


class WishlistView(AccountAPIView):
    def get(self, request):
        pagination = WishlistPagination()
        rows = pagination.paginate_queryset(_visible_wishlist_items(request.user).order_by('-pk'), request)
        return pagination.get_paginated_response([wishlist_data(request, item) for item in rows])


class WishlistAddView(AccountAPIView):
    def post(self, request, pk):
        product = get_object_or_404(Product.objects.prefetch_related('images'), pk=pk, status=Product.Status.AVAILABLE)
        if product.seller_id == request.user.pk:
            raise ValidationError({'detail': 'You cannot save your own listing.'})
        image = product.primary_image
        item, _ = WishlistItem.objects.update_or_create(
            user=request.user, product_key=product.slug,
            defaults={'title': product.title, 'condition': product.get_condition_display(),
                      'price': product.price, 'image': image.image.url if image else '', 'removed': False},
        )
        return Response(wishlist_data(request, item))


class WishlistItemView(AccountAPIView):
    def delete(self, request, pk):
        item = get_object_or_404(WishlistItem, user=request.user, pk=pk, removed=False)
        item.removed = True
        item.save(update_fields=['removed'])
        return Response(status=204)


class WishlistRestoreView(AccountAPIView):
    def post(self, request, pk):
        item = get_object_or_404(WishlistItem, user=request.user, pk=pk, removed=True)
        item.removed = False
        item.save(update_fields=['removed'])
        return Response(wishlist_data(request, item))


class ResendVerificationView(AccountAPIView):
    def post(self, request):
        if user_data(request, request.user)['email_verified']:
            return Response({'detail': 'Email is already verified.'})
        if not request.user.email:
            raise ValidationError({'detail': 'Your account has no email. Please contact support.'})
        try:
            sent = _send_verification_email(request, request.user)
        except (SMTPException, OSError):
            return Response({'detail': 'Email delivery failed. Try again after one minute.'}, status=503)
        if not sent:
            raise Throttled(wait=60)
        return Response({'detail': 'Verification email sent. The link expires in 24 hours.'})


class ChangePasswordView(AccountAPIView):
    def post(self, request):
        if not request.user.has_usable_password():
            raise ValidationError({'detail': 'This account uses external sign-in.'})
        form = valid(PasswordChangeForm(request.user, request.data))
        form.save()
        Token.objects.filter(user=request.user).delete()
        return Response({'detail': 'Password changed. Please sign in again.'})


class ResetPasswordView(PublicAPIView):
    def post(self, request):
        email = str(request.data.get('email', '')).strip().casefold()
        check_rate(request, 'reset', email, 3, 20, 3600)
        form = valid(PasswordResetForm(request.data))
        try:
            form.save(request=request, use_https=settings.PRODUCTION or request.is_secure())
        except (SMTPException, OSError):
            # Same response for existing/unknown accounts to avoid account enumeration.
            pass
        return Response({'detail': 'If an eligible account exists, a reset link will be sent to its email.'})
