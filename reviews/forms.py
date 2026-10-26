from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review

        fields = [
            "rating",
            "title",
            "comment",
            "is_anonymous",
        ]

        widgets = {
            "rating": forms.Select(choices=[
                (1, "1 star"),
                (2, "2 stars"),
                (3, "3 stars"),
                (4, "4 stars"),
                (5, "5 stars"),
            ]),
            "comment": forms.Textarea(attrs={"rows": 4}),
        }

        labels = {
            "rating": "Rating",
            "title": "Experience summary",
            "comment": "Share your experience",
            "is_anonymous": "Post this review anonymously",
        }