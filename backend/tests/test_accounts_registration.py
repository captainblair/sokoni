import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status

from tests.conftest import DEFAULT_PASSWORD

User = get_user_model()

pytestmark = pytest.mark.django_db


def registration_payload(**overrides):
    payload = {
        "email": "newtrader@example.com",
        "full_name": "New Trader",
        "phone_number": "+254712345678",
        "password": DEFAULT_PASSWORD,
        "password_confirm": DEFAULT_PASSWORD,
    }
    payload.update(overrides)
    return payload


def test_registration_creates_user_and_returns_tokens(api_client):
    response = api_client.post(reverse("auth-register"), registration_payload(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert "access" in response.data
    assert "refresh" in response.data
    assert response.data["user"]["email"] == "newtrader@example.com"
    assert "password" not in response.data["user"]

    user = User.objects.get(email="newtrader@example.com")
    assert user.check_password(DEFAULT_PASSWORD)


def test_registration_normalises_email_case(api_client):
    api_client.post(
        reverse("auth-register"),
        registration_payload(email="MixedCase@Example.com"),
        format="json",
    )

    assert User.objects.filter(email="mixedcase@example.com").exists()


def test_registration_rejects_duplicate_email(api_client, user_factory):
    user_factory(email="taken@example.com")

    response = api_client.post(
        reverse("auth-register"),
        registration_payload(email="taken@example.com"),
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


def test_registration_rejects_mismatched_passwords(api_client):
    response = api_client.post(
        reverse("auth-register"),
        registration_payload(password_confirm="something-else-entirely"),
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password_confirm" in response.data


def test_registration_rejects_weak_password(api_client):
    response = api_client.post(
        reverse("auth-register"),
        registration_payload(password="12345", password_confirm="12345"),
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data


def test_registration_rejects_invalid_phone_number(api_client):
    response = api_client.post(
        reverse("auth-register"),
        registration_payload(phone_number="not-a-phone"),
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "phone_number" in response.data
