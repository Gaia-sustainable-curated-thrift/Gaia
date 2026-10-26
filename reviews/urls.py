from django.urls import path
from . import views


app_name = "reviews"

urlpatterns = [
    path(
        "seller/<int:seller_id>/",
        views.seller_reviews,
        name="seller_reviews",
    ),
]