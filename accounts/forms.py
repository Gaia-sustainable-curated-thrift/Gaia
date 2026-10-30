from io import BytesIO
from PIL import Image, ImageOps
from django import forms
from django.core.files.base import ContentFile
from .avatars import schedule_avatar_delete
from .identity import reserved_username
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.text import slugify

User = get_user_model()


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Email', widget=forms.TextInput(attrs={'placeholder': 'Enter your email', 'autocomplete': 'username'}))

    def clean(self):
        identifier = self.cleaned_data.get('username', '')
        if '@' in identifier:
            matches = User.objects.filter(email__iexact=identifier)
            if matches.count() == 1:
                self.cleaned_data['username'] = matches.get().username
        return super().clean()


class RegisterForm(UserCreationForm):
    full_name = forms.CharField(max_length=150, label='Full name')
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['full_name', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password2'].label = 'Confirm password'
        self.fields['full_name'].widget.attrs['autocomplete'] = 'name'
        self.fields['email'].widget.attrs['autocomplete'] = 'email'

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['full_name']
        base = slugify(user.first_name).replace('-', '')[:120] or 'gaia'
        username, suffix = base, 1
        while reserved_username(username) or User.objects.filter(username__iexact=username).exists():
            username = f'{base}{suffix}'
            suffix += 1
        user.username = username
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    avatar = forms.ImageField(
        label='Profile photo', required=False,
        widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp', 'data-avatar-input': ''}),
        help_text='JPG, PNG or WebP. Maximum 2 MB. Your photo will be cropped to a square.',
    )
    full_name = forms.CharField(max_length=150, label='Full name')
    phone = forms.CharField(max_length=30, label='Phone number', widget=forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}))
    city = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'autocomplete': 'address-level2'}))
    country = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'autocomplete': 'country-name'}))
    email = forms.EmailField(disabled=True, required=False)

    class Meta:
        model = User
        fields = ['avatar', 'full_name', 'username', 'email', 'phone', 'city', 'country']

    def clean_avatar(self):
        upload = self.cleaned_data.get('avatar')
        if not upload:
            return None
        if upload.size > 2 * 1024 * 1024:
            raise forms.ValidationError('Choose a photo smaller than or equal to 2 MB.')
        if upload.image.format not in {'JPEG', 'PNG', 'WEBP'}:
            raise forms.ValidationError('Use a JPG, PNG or WebP image.')
        if max(upload.image.size) > 4096:
            raise forms.ValidationError('Your photo must be no larger than 4096 pixels on either side.')
        try:
            upload.seek(0)
            with Image.open(upload) as image:
                image = ImageOps.exif_transpose(image)
                image = ImageOps.fit(image.convert('RGBA'), (512, 512))
                background = Image.new('RGB', image.size, 'white')
                background.paste(image, mask=image.getchannel('A'))
                output = BytesIO()
                background.save(output, format='JPEG', quality=85)
        except (OSError, ValueError):
            raise forms.ValidationError('This image could not be processed. Please choose another photo.')
        return ContentFile(output.getvalue(), name='avatar.jpg')

    def clean_username(self):
        username = self.cleaned_data['username']
        if reserved_username(username) and not (self.instance.is_staff and username == self.instance.username):
            raise forms.ValidationError('This username is reserved for the GAIA support team.')
        if User.objects.filter(username__iexact=username).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data['full_name']
        user.last_name = ''
        if commit:
            user.save()
            profile = user.profile
            for field in ['phone', 'city', 'country']:
                setattr(profile, field, self.cleaned_data[field])
            old_avatar = profile.avatar
            if self.cleaned_data.get('avatar'):
                profile.avatar = self.cleaned_data['avatar']
            profile.save()
            if old_avatar and old_avatar.name != profile.avatar.name:
                schedule_avatar_delete(old_avatar)
        return user


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label='Current password', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )
    confirmation = forms.CharField(label='Type DELETE to confirm', max_length=6)
    acknowledge = forms.BooleanField(
        label='I understand that my account and the data listed above will be permanently deleted.'
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        if not user.has_usable_password():
            self.fields.pop('password')

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise forms.ValidationError('Your password is incorrect. Please try again.')
        return password

    def clean_confirmation(self):
        if self.cleaned_data['confirmation'] != 'DELETE':
            raise forms.ValidationError('Type DELETE exactly to confirm account deletion.')
        return 'DELETE'
