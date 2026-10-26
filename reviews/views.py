from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404, render

from .models import Review


def seller_reviews(request, seller_id):
    seller = get_object_or_404(
        get_user_model(),
        pk=seller_id,
    )

    reviews = Review.objects.filter(seller=seller)

    context = {
        "seller": seller,
        "reviews": reviews,
    }

    return render(request, "reviews/seller_reviews.html", context)