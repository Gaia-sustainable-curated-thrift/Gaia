from django import forms
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
        while User.objects.filter(username__iexact=username).exists():
            username = f'{base}{suffix}'
            suffix += 1
        user.username = username
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150, label='Full name')
    phone = forms.CharField(max_length=30, required=False, label='Phone number')
    city = forms.CharField(max_length=100, required=False)
    country = forms.CharField(max_length=100, required=False)
    email = forms.EmailField(disabled=True, required=False)

    class Meta:
        model = User
        fields = ['full_name', 'username', 'email', 'phone', 'city', 'country']

    def clean_username(self):
        username = self.cleaned_data['username']
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
            profile.save()
        return user
