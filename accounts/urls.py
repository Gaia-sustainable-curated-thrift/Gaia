from django.urls import path
from django.contrib.auth import views
from . import views as account_views


urlpatterns = [
    path(
        "login/",
        views.LoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login"
    ),

    path(
        "logout/",
        views.LogoutView.as_view(),
        name="logout"
    ),

    path(
        "register/",
        account_views.register,
        name="register"
    ),
]