from django.urls import path
from . import views


app_name = "reviews"

urlpatterns = [
    path(
        "seller/<int:seller_id>/",
        views.seller_reviews,
        name="seller_reviews",
    ),

    path(
        "seller/<int:seller_id>/create/",
        views.create_review,
        name="create_review",
    ),

    path(
        "<int:review_id>/edit/",
        views.edit_review,
        name="edit_review",
    ),

    path(
        "<int:review_id>/delete/",
        views.delete_review,
        name="delete_review",
    ),

]