
from django.urls import path

from . import views

app_name = "transaction"

urlpatterns = [
    path("checkout/", views.checkout, name="checkout"),
    path("shipping/", views.shipping, name="shipping"),
    path("payment/", views.payment, name="payment"),
    path("confirmation/", views.confirmation, name="confirmation"),
]
