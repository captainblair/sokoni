import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

DEFAULT_PASSWORD = "Sokoni-Test-Pass-2026"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory(db):
    def create(email="trader@example.com", password=DEFAULT_PASSWORD, **extra):
        return User.objects.create_user(email=email, password=password, **extra)

    return create


@pytest.fixture
def user(user_factory):
    return user_factory(full_name="Amina Trader")


@pytest.fixture
def authenticated_client(api_client, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return api_client
