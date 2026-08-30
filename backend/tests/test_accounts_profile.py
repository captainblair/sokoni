import pytest
from django.urls import reverse
from rest_framework import status

from tests.conftest import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db

NEW_PASSWORD = "Another-Strong-Pass-2026"


def test_me_returns_authenticated_user(authenticated_client, user):
    response = authenticated_client.get(reverse("auth-me"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["email"] == user.email
    assert response.data["full_name"] == "Amina Trader"


def test_me_requires_authentication(api_client):
    response = api_client.get(reverse("auth-me"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_me_updates_own_profile_only(authenticated_client, user, user_factory):
    other = user_factory(email="other@example.com", full_name="Other Trader")

    response = authenticated_client.patch(
        reverse("auth-me"),
        {"full_name": "Amina Updated", "id": str(other.id), "email": "hijack@example.com"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    user.refresh_from_db()
    other.refresh_from_db()

    assert user.full_name == "Amina Updated"
    assert user.email == "trader@example.com"
    assert other.full_name == "Other Trader"


def test_password_change_succeeds_and_old_password_stops_working(
    authenticated_client, api_client, user
):
    response = authenticated_client.post(
        reverse("auth-password-change"),
        {"current_password": DEFAULT_PASSWORD, "new_password": NEW_PASSWORD},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK

    old_login = api_client.post(
        reverse("auth-login"),
        {"email": user.email, "password": DEFAULT_PASSWORD},
        format="json",
    )
    assert old_login.status_code == status.HTTP_401_UNAUTHORIZED

    new_login = api_client.post(
        reverse("auth-login"),
        {"email": user.email, "password": NEW_PASSWORD},
        format="json",
    )
    assert new_login.status_code == status.HTTP_200_OK


def test_password_change_rejects_wrong_current_password(authenticated_client):
    response = authenticated_client.post(
        reverse("auth-password-change"),
        {"current_password": "definitely-wrong", "new_password": NEW_PASSWORD},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "current_password" in response.data


def test_password_change_rejects_weak_new_password(authenticated_client):
    response = authenticated_client.post(
        reverse("auth-password-change"),
        {"current_password": DEFAULT_PASSWORD, "new_password": "1234"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "new_password" in response.data


def test_health_endpoint_stays_public(api_client):
    response = api_client.get(reverse("health-check"))

    assert response.status_code == status.HTTP_200_OK
