import pytest
from django.urls import reverse
from rest_framework import status

from tests.conftest import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


def login(api_client, email, password=DEFAULT_PASSWORD):
    return api_client.post(
        reverse("auth-login"),
        {"email": email, "password": password},
        format="json",
    )


def test_login_returns_token_pair_and_user(api_client, user):
    response = login(api_client, user.email)

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" in response.data
    assert response.data["user"]["email"] == user.email


def test_login_is_case_insensitive_on_email(api_client, user):
    response = login(api_client, user.email.upper())

    assert response.status_code == status.HTTP_200_OK


def test_login_rejects_wrong_password(api_client, user):
    response = login(api_client, user.email, password="wrong-password")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "access" not in response.data


def test_login_rejects_inactive_user(api_client, user):
    user.is_active = False
    user.save(update_fields=["is_active"])

    response = login(api_client, user.email)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_returns_new_access_token(api_client, user):
    refresh = login(api_client, user.email).data["refresh"]

    response = api_client.post(reverse("auth-refresh"), {"refresh": refresh}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data


def test_logout_blacklists_refresh_token(authenticated_client, api_client, user):
    refresh = login(api_client, user.email).data["refresh"]

    logout_response = authenticated_client.post(
        reverse("auth-logout"), {"refresh": refresh}, format="json"
    )
    assert logout_response.status_code == status.HTTP_204_NO_CONTENT

    reuse_response = api_client.post(reverse("auth-refresh"), {"refresh": refresh}, format="json")
    assert reuse_response.status_code == status.HTTP_401_UNAUTHORIZED


def test_logout_requires_authentication(api_client, user):
    refresh = login(api_client, user.email).data["refresh"]

    response = api_client.post(reverse("auth-logout"), {"refresh": refresh}, format="json")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_verify_endpoint_accepts_valid_access_token(api_client, user):
    access = login(api_client, user.email).data["access"]

    response = api_client.post(reverse("auth-verify"), {"token": access}, format="json")

    assert response.status_code == status.HTTP_200_OK
