from contextlib import contextmanager
from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import redirect


@contextmanager
def unique_email_signup(request, user):
    try:
        with transaction.atomic():
            yield
    except IntegrityError:
        email = (user.email or '').strip()
        if email and get_user_model().objects.filter(email__iexact=email).exists():
            messages.error(request, 'An account with this email already exists. Please log in and connect Google from your existing account.')
            raise ImmediateHttpResponse(redirect('login'))
        raise


class AccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        with unique_email_signup(request, user):
            return super().save_user(request, user, form, commit=commit)


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        with unique_email_signup(request, sociallogin.user):
            return super().save_user(request, sociallogin, form=form)
