import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_health_check_returns_ok_when_database_is_up():
    client = APIClient()
    response = client.get(reverse("health-check"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"
    assert response.data["service"] == "sokoni-api"
    assert response.data["database"] == "up"


def test_settings_module_loads():
    from django.conf import settings

    assert settings.ROOT_URLCONF == "config.urls"
    assert "apps.core" in settings.INSTALLED_APPS or any(
        "apps.core" in str(app) for app in settings.INSTALLED_APPS
    )
