from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.views.generic import RedirectView
from .media import uploaded_image


def not_found(request, exception=None):
    return render(request, "404.html", status=404)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("media/<path:name>", uploaded_image, name="uploaded_image"),

    path(
        "accounts/",
        include("accounts.urls")
    ),

    # URL django-allauth (Google login: /accounts/google/login/)
    path("accounts/", include("allauth.urls")),

    path("products/", include("products.urls")),
    path("transaction/", include("transaction.urls")),
    path("chat/", include("chat.urls")),
    path("reviews/", include("reviews.urls")),

    # Pratinjau halaman 404 (produksi otomatis pakai templates/404.html)
    path("404/", not_found, name="preview-404"),
    path("", RedirectView.as_view(pattern_name="products:home", permanent=False)),
]
