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
def other_user(user_factory):
    return user_factory(email="rival@example.com", full_name="Rival Trader")


def _client_for(user):
    from rest_framework_simplejwt.tokens import RefreshToken

    client = APIClient()
    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")
    return client


@pytest.fixture
def authenticated_client(user):
    return _client_for(user)


@pytest.fixture
def client_for():
    """Builds an authenticated client for any user."""
    return _client_for


@pytest.fixture
def business_factory(db):
    from apps.businesses.services import create_business

    def create(user, name="Amina Groceries", **extra):
        return create_business(user=user, name=name, **extra)

    return create


@pytest.fixture
def business(business_factory, user):
    return business_factory(user)


@pytest.fixture
def other_business(business_factory, other_user):
    return business_factory(other_user, name="Rival Stores")
