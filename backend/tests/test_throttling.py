"""The doors that get abused first are the ones that close first."""

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status

from apps.core.throttles import AgentRateThrottle, AuthRateThrottle
from tests.conftest import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def one_auth_per_minute(monkeypatch):
    monkeypatch.setattr(AuthRateThrottle, "rate", "1/min", raising=False)


@pytest.fixture
def one_agent_per_minute(monkeypatch):
    monkeypatch.setattr(AgentRateThrottle, "rate", "1/min", raising=False)


def test_login_is_throttled_after_the_first_try(
    api_client, user, one_auth_per_minute
):
    url = reverse("auth-login")
    payload = {"email": user.email, "password": DEFAULT_PASSWORD}

    first = api_client.post(url, payload, format="json")
    second = api_client.post(url, payload, format="json")

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_agent_execution_is_throttled(
    authenticated_client, business, one_agent_per_minute
):
    url = reverse("agent-execute")
    payload = {"tool": "get_cash_position", "parameters": {}}

    first = authenticated_client.post(url, payload, format="json")
    second = authenticated_client.post(url, payload, format="json")

    assert first.status_code == status.HTTP_200_OK
    assert second.status_code == status.HTTP_429_TOO_MANY_REQUESTS


def test_ordinary_reads_are_not_pinched_by_the_auth_limit(
    authenticated_client, business
):
    url = reverse("cash-position")

    for _ in range(5):
        assert authenticated_client.get(url).status_code == status.HTTP_200_OK
