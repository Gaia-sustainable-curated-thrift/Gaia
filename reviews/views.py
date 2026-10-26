from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ReviewForm
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

@login_required(login_url="login")
def create_review(request, seller_id):
    seller = get_object_or_404(get_user_model(), pk=seller_id)

    if seller == request.user:
        raise PermissionDenied("Kamu tidak bisa mereview diri sendiri.")

    if request.method == "POST":
        form = ReviewForm(request.POST)

        if form.is_valid():
            review = form.save(commit=False)
            review.reviewer = request.user
            review.seller = seller
            review.save()

            return redirect(
                "reviews:seller_reviews",
                seller_id=seller.pk,
            )
    else:
        form = ReviewForm()

    context = {
        "form": form,
        "seller": seller,
    }

    return render(request, "reviews/review_form.html", context)

@login_required(login_url="login")
def edit_review(request, review_id):
    review = get_object_or_404(
        Review,
        pk=review_id,
        reviewer=request.user,
    )

    if request.method == "POST":
        form = ReviewForm(request.POST, instance=review)

        if form.is_valid():
            form.save()

            return redirect(
                "reviews:seller_reviews",
                seller_id=review.seller_id,
            )
    else:
        form = ReviewForm(instance=review)

    context = {
        "form": form,
        "seller": review.seller,
        "is_edit": True,
    }

    return render(request, "reviews/review_form.html", context)

@login_required(login_url="login")
def delete_review(request, review_id):
    review = get_object_or_404(
        Review,
        pk=review_id,
        reviewer=request.user,
    )

    if request.method == "POST":
        seller_id = review.seller_id
        review.delete()

        return redirect(
            "reviews:seller_reviews",
            seller_id=seller_id,
        )

    context = {
        "review": review,
        "seller": review.seller,
    }

    return render(request, "reviews/review_confirm_delete.html", context)