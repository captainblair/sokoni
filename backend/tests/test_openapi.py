"""The published contract is generated from the real serializers."""

import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db

SCHEMA = reverse("schema")
SWAGGER = reverse("swagger-ui")
REDOC = reverse("redoc")

REQUIRED_PATHS = {
    "/api/v1/health/",
    "/api/v1/auth/register/",
    "/api/v1/auth/login/",
    "/api/v1/businesses/",
    "/api/v1/parties/",
    "/api/v1/products/",
    "/api/v1/transactions/",
    "/api/v1/debts/",
    "/api/v1/finance/cash-position/",
    "/api/v1/finance/daily-brief/",
    "/api/v1/agent/tools/",
    "/api/v1/agent/execute/",
    "/api/v1/audit-events/",
}


def schema(client):
    return client.get(SCHEMA, HTTP_ACCEPT="application/json")


def test_the_schema_is_public(api_client):
    response = schema(api_client)

    assert response.status_code == status.HTTP_200_OK


def test_the_schema_describes_every_built_surface(api_client):
    response = schema(api_client)

    paths = set(response.data["paths"])
    missing = REQUIRED_PATHS - paths
    assert missing == set(), f"Schema is missing {missing}"


def test_the_schema_declares_bearer_auth(api_client):
    response = schema(api_client)

    schemes = response.data["components"]["securitySchemes"]
    assert any(
        scheme.get("scheme") == "bearer" or scheme.get("type") == "http"
        for scheme in schemes.values()
    )


def test_swagger_ui_is_public(api_client):
    assert api_client.get(SWAGGER).status_code == status.HTTP_200_OK


def test_redoc_is_public(api_client):
    assert api_client.get(REDOC).status_code == status.HTTP_200_OK
