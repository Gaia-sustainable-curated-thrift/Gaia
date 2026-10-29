
from django import forms


class ShippingAddressForm(forms.Form):
    recipient = forms.CharField(
        max_length=150,
        label="Recipient name",
        widget=forms.TextInput(attrs={"placeholder": "Full name"})
    )

    phone = forms.CharField(
        max_length=30,
        label="Phone number",
        widget=forms.TextInput(attrs={"placeholder": "e.g. 08xxxxxxxxxx"})
    )

    address = forms.CharField(
        label="Full address",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "Street, building, house number, etc."
        })
    )

    city = forms.CharField(
        max_length=100,
        label="City"
    )

    postal_code = forms.CharField(
        max_length=20,
        label="Postal code"
    )

    country = forms.CharField(
        max_length=100,
        label="Country",
        initial="Indonesia"
    )


class PaymentMethodForm(forms.Form):
    PAYMENT_CHOICES = [
        ("bank_transfer", "Bank Transfer"),
        ("e_wallet", "E-Wallet"),
        ("cod", "Cash on Delivery (COD)"),
    ]

    payment_method = forms.ChoiceField(
        choices=PAYMENT_CHOICES,
        widget=forms.RadioSelect,
        label="Choose payment method",
    )
