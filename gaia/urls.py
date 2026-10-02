from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render


def home(request):
    return render(request, "landing.html")


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "accounts/",
        include("accounts.urls")
    ),

    # URL django-allauth (Google login: /accounts/google/login/)
    path("accounts/", include("allauth.urls")),

    path("", home),
]
