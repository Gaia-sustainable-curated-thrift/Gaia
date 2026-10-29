from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, Exists, OuterRef
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ReviewForm, ReviewReportForm, SellerReplyForm
from .models import Review, ReviewReport
from .purchases import eligible_orders
from accounts.models import AccountOrder


def _is_ajax(request):
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


def _get_seller(seller_id):
    seller = get_object_or_404(get_user_model(), pk=seller_id, is_active=True)
    # No separate seller role exists yet. Listings or historical reviews
    # identify a seller without changing the accounts module.
    if not seller.products.exists() and not seller.received_reviews.exists() and not seller.sales_orders.exists():
        raise Http404("Seller not found.")
    return seller


def _review_context(request, seller):
    all_reviews = Review.objects.filter(seller=seller)
    summary = all_reviews.aggregate(average_rating=Avg("rating"), total_reviews=Count("pk"))
    total = summary["total_reviews"]
    counts = dict(all_reviews.order_by().values_list("rating").annotate(count=Count("pk")))
    breakdown = [
        {"rating": star, "count": counts.get(star, 0),
         "percent": round(counts.get(star, 0) * 100 / total) if total else 0}
        for star in range(5, 0, -1)
    ]

    selected_rating = request.GET.get("rating", "")
    reviews = all_reviews.select_related("reviewer", "seller", "order").annotate(
        helpful_count=Count("helpful_by", distinct=True)
    )
    if selected_rating in ["1", "2", "3", "4", "5"]:
        reviews = reviews.filter(rating=int(selected_rating))
    else:
        selected_rating = ""

    if request.user.is_authenticated:
        votes = Review.helpful_by.through.objects.filter(
            review_id=OuterRef("pk"), user_id=request.user.pk,
        )
        reports = ReviewReport.objects.filter(review_id=OuterRef("pk"), reporter=request.user)
        reviews = reviews.annotate(has_voted=Exists(votes), has_reported=Exists(reports))

    sort = request.GET.get("sort", "newest")
    orderings = {
        "newest": ["-created_at", "-pk"],
        "helpful": ["-helpful_count", "-created_at", "-pk"],
        "rating": ["-rating", "-created_at", "-pk"],
    }
    if sort not in orderings:
        sort = "newest"
    reviews = reviews.order_by(*orderings[sort])
    page = Paginator(reviews, 6).get_page(request.GET.get("page"))
    params = {"sort": sort}
    if selected_rating:
        params["rating"] = selected_rating
    return {
        "seller": seller, "reviews": page, "page_obj": page,
        **summary, "rating_breakdown": breakdown,
        "selected_rating": selected_rating, "selected_sort": sort,
        "filtered_count": page.paginator.count, "page_query": urlencode(params),
        "reply_form": SellerReplyForm(), "report_form": ReviewReportForm(),
    }


def _review_page(request, seller, *, account=False):
    context = _review_context(request, seller)
    context["is_account"] = account
    if _is_ajax(request):
        response = JsonResponse({
            "html": render_to_string("reviews/_review_panel.html", context, request=request)
        })
    else:
        context.update(
            title="Seller Reviews", subtitle="See what others say about your store.", active="reviews",
        )
        template = "reviews/account_reviews.html" if account else "reviews/seller_reviews.html"
        response = render(request, template, context)
    # HTML contains ownership controls and login-dependent reviewer identities.
    response["Cache-Control"] = "private, no-store"
    return response


@require_http_methods(["GET"])
def seller_reviews(request, seller_id):
    return _review_page(request, _get_seller(seller_id))


@login_required(login_url="login")
@require_http_methods(["GET"])
def account_reviews(request):
    return _review_page(request, _get_seller(request.user.pk), account=True)


def _saved(request, seller_id, text):
    url = reverse("reviews:seller_reviews", args=[seller_id])
    if _is_ajax(request):
        return JsonResponse({"ok": True, "message": text, "redirect_url": url})
    messages.success(request, text)
    return redirect(url)


def _render_form(request, template, context):
    if _is_ajax(request) and request.method == "POST":
        return JsonResponse({
            "ok": False,
            "html": render_to_string("reviews/_form_fields.html", context, request=request),
        }, status=400)
    return render(request, template, context)


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def create_review(request, seller_id, order_id=None):
    seller = _get_seller(seller_id)
    if seller == request.user:
        raise PermissionDenied("Kamu tidak bisa mereview diri sendiri.")
    orders = eligible_orders(request.user, seller)
    if order_id is not None:
        orders = orders.filter(pk=order_id)
    if not orders.exists():
        return render(request, 'reviews/purchase_required.html', {'seller': seller}, status=403)
    data = request.POST.copy() if request.method == 'POST' else None
    if data is not None and 'order' not in data and orders.count() == 1:
        data['order'] = orders.first().pk
    form = ReviewForm(data, orders=orders)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            order = AccountOrder.objects.select_for_update().get(pk=form.cleaned_data['order'].pk)
            if (order.user_id != request.user.pk or order.seller_id != seller.pk
                    or order.status != AccountOrder.Status.COMPLETED
                    or Review.objects.filter(order=order).exists()):
                form.add_error('order', 'This order is no longer eligible for a review.')
            else:
                review = form.save(commit=False)
                review.order = order
                review.reviewer = request.user
                review.seller = seller
                review.save()
                return _saved(request, seller.pk, "Your seller review has been published.")
    return _render_form(request, "reviews/review_form.html", {"form": form, "seller": seller})


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def create_order_review(request, order_id):
    order = get_object_or_404(AccountOrder, pk=order_id, user=request.user)
    if order.seller_id is None:
        return render(request, 'reviews/purchase_required.html', {}, status=403)
    existing = Review.objects.filter(order=order, reviewer=request.user).first()
    if existing:
        return redirect('reviews:edit_review', review_id=existing.pk)
    return create_review(request, order.seller_id, order_id=order.pk)


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def edit_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id, reviewer=request.user)
    form = ReviewForm(request.POST if request.method == "POST" else None, instance=review)
    if request.method == "POST" and form.is_valid():
        form.save()
        return _saved(request, review.seller_id, "Your review has been updated.")
    return _render_form(request, "reviews/review_form.html", {
        "form": form, "seller": review.seller, "is_edit": True,
    })


@login_required(login_url="login")
@require_http_methods(["GET", "POST"])
def delete_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id, reviewer=request.user)
    if request.method == "POST":
        seller_id = review.seller_id
        review.delete()
        return _saved(request, seller_id, "Your review has been deleted.")
    return render(request, "reviews/review_confirm_delete.html", {"review": review, "seller": review.seller})


@login_required(login_url="login")
@require_POST
def toggle_helpful(request, review_id):
    review = get_object_or_404(Review, pk=review_id)
    if request.user.pk in [review.reviewer_id, review.seller_id]:
        raise PermissionDenied("You cannot vote on your own review or your store's review.")
    vote, created = Review.helpful_by.through.objects.get_or_create(
        review_id=review.pk, user_id=request.user.pk,
    )
    if not created:
        vote.delete()
    return _saved(request, review.seller_id, "Helpful vote added." if created else "Helpful vote removed.")


@login_required(login_url="login")
@require_POST
def seller_reply(request, review_id):
    review = get_object_or_404(Review, pk=review_id, seller=request.user)
    form = SellerReplyForm(request.POST)
    if form.is_valid():
        review.seller_reply = form.cleaned_data["reply"]
        review.seller_replied_at = timezone.now()
        review.save(update_fields=["seller_reply", "seller_replied_at"])
        return _saved(request, review.seller_id, "Your reply has been saved.")
    return _action_error(request, review, form, "Reply to review", "reviews:seller_reply")


@login_required(login_url="login")
@require_POST
def delete_reply(request, review_id):
    review = get_object_or_404(Review, pk=review_id, seller=request.user)
    review.seller_reply = ""
    review.seller_replied_at = None
    review.save(update_fields=["seller_reply", "seller_replied_at"])
    return _saved(request, review.seller_id, "Your reply has been removed.")


@login_required(login_url="login")
@require_POST
def report_review(request, review_id):
    review = get_object_or_404(Review, pk=review_id)
    if review.reviewer_id == request.user.pk:
        raise PermissionDenied("You cannot report your own review.")
    form = ReviewReportForm(request.POST)
    if form.is_valid():
        ReviewReport.objects.get_or_create(
            review=review, reporter=request.user, defaults=form.cleaned_data,
        )
        return _saved(request, review.seller_id, "Report received. An administrator can review it.")
    return _action_error(request, review, form, "Report review", "reviews:report_review")


def _action_error(request, review, form, title, action):
    if _is_ajax(request):
        return JsonResponse({"ok": False, "errors": form.errors}, status=400)
    return render(request, "reviews/action_form.html", {
        "review": review, "seller": review.seller, "form": form,
        "title": title, "action_url": reverse(action, args=[review.pk]),
    }, status=400)
