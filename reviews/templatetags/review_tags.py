from django import template
from django.db.models import Avg, Count
from reviews.models import Review

register = template.Library()


@register.inclusion_tag("reviews/_product_rating.html")
def seller_rating(seller):
    summary = Review.objects.filter(seller=seller).aggregate(
        average_rating=Avg("rating"), total_reviews=Count("pk"),
    )
    average = summary['average_rating'] or 0
    star_fill = [round(max(0, min(1, average - index)) * 100) for index in range(5)]
    return {"seller": seller, **summary, "star_fill": star_fill}


@register.inclusion_tag("reviews/_account_nav.html")
def seller_reviews_nav(user, active=""):
    is_seller = user.is_authenticated and (
        user.products.exists() or user.received_reviews.exists() or user.sales_orders.exists()
    )
    return {"is_seller": is_seller, "active": active}


@register.inclusion_tag('reviews/_order_action.html')
def review_order_action(order, user):
    eligible = bool(user.is_authenticated and order.user_id == user.pk
                    and order.status == 'completed' and order.seller_id
                    and order.seller_id != user.pk and order.seller.is_active)
    review = Review.objects.filter(order=order, reviewer=user).first() if eligible else None
    return {'order': order, 'eligible': eligible, 'existing_review': review}
