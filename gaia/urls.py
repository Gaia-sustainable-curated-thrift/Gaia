from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render
from django.views.generic import RedirectView


def not_found(request, exception=None):
    return render(request, "404.html", status=404)


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "accounts/",
        include("accounts.urls")
    ),

    # URL django-allauth (Google login: /accounts/google/login/)
    path("accounts/", include("allauth.urls")),

    path("products/", include("products.urls")),

    path("chat/", include("chat.urls")),

    # Pratinjau halaman 404 (produksi otomatis pakai templates/404.html)
    path("404/", not_found, name="preview-404"),

    path("", RedirectView.as_view(pattern_name="products:home", permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
