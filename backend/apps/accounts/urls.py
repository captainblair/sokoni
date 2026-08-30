from django.urls import path

from apps.accounts.views import (
    CurrentUserView,
    LoginView,
    LogoutView,
    PasswordChangeView,
    RefreshView,
    RegistrationView,
    VerifyView,
)

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="auth-register"),
    path("login/", LoginView.as_view(), name="auth-login"),
    path("refresh/", RefreshView.as_view(), name="auth-refresh"),
    path("verify/", VerifyView.as_view(), name="auth-verify"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", CurrentUserView.as_view(), name="auth-me"),
    path("password/change/", PasswordChangeView.as_view(), name="auth-password-change"),
]
