from django import template
from django.db.models import Avg, Count
from reviews.models import Review

register = template.Library()


@register.inclusion_tag("reviews/_product_rating.html")
def seller_rating(seller):
    summary = Review.objects.filter(seller=seller).aggregate(
        average_rating=Avg("rating"), total_reviews=Count("pk"),
    )
    return {"seller": seller, **summary}


@register.inclusion_tag("reviews/_account_nav.html")
def seller_reviews_nav(user, active=""):
    is_seller = user.is_authenticated and (
        user.products.exists() or user.received_reviews.exists()
    )
    return {"is_seller": is_seller, "active": active}
