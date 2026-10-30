from django import forms
from .models import Review, ReviewReport


class ReviewForm(forms.ModelForm):
    def __init__(self, *args, orders=None, **kwargs):
        super().__init__(*args, **kwargs)
        if orders is not None:
            self.fields['order'] = forms.ModelChoiceField(
                queryset=orders, label='Completed purchase',
                help_text='Choose the completed order for this seller.',
            )
            self.fields['order'].label_from_instance = lambda order: f'{order.number} — {order.title}'
            first = orders.first()
            if first:
                self.initial['order'] = first.pk

    class Meta:
        model = Review
        fields = [
            "rating", "title", "comment", "is_anonymous",
            "is_friendly", "is_responsive", "is_trustworthy",
        ]
        widgets = {
            "is_anonymous": forms.CheckboxInput(attrs={"role": "switch"}),
            "rating": forms.RadioSelect(choices=[
                (1, "1 star"), (2, "2 stars"), (3, "3 stars"),
                (4, "4 stars"), (5, "5 stars"),
            ]),
            "title": forms.TextInput(attrs={"placeholder": "e.g. Friendly and quick to help"}),
            "comment": forms.Textarea(attrs={
                "rows": 5,
                "placeholder": "How did the seller communicate, help you, and build trust?",
            }),
        }
        labels = {
            "rating": "How was your experience with this seller?",
            "title": "Experience summary",
            "comment": "Share your experience",
            "is_anonymous": "Post this review anonymously",
            "is_friendly": "Friendly & polite",
            "is_responsive": "Helpful & responsive",
            "is_trustworthy": "Honest & trustworthy",
        }


class SellerReplyForm(forms.Form):
    reply = forms.CharField(
        max_length=1000, label="Your reply",
        widget=forms.Textarea(attrs={"rows": 3}),
    )


class ReviewReportForm(forms.ModelForm):
    class Meta:
        model = ReviewReport
        fields = ["reason", "details"]
        widgets = {"details": forms.Textarea(attrs={"rows": 3})}
