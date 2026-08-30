import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db

ACTIVE_URL = reverse("business-active")


def activate_url(business):
    return reverse("business-activate", args=[business.id])


def test_activate_sets_the_working_business(authenticated_client, business_factory, user):
    first = business_factory(user, name="First Shop")
    second = business_factory(user, name="Second Shop")

    response = authenticated_client.post(activate_url(second))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == str(second.id)

    user.refresh_from_db()
    assert user.active_business_id == second.id
    assert user.active_business_id != first.id


def test_active_endpoint_returns_the_selected_business(authenticated_client, business):
    response = authenticated_client.get(ACTIVE_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == str(business.id)


def test_active_endpoint_reports_when_nothing_is_selected(authenticated_client):
    response = authenticated_client.get(ACTIVE_URL)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_archiving_the_active_business_clears_the_selection(authenticated_client, business):
    authenticated_client.delete(reverse("business-detail", args=[business.id]))

    response = authenticated_client.get(ACTIVE_URL)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_profile_exposes_the_active_business(authenticated_client, business):
    response = authenticated_client.get(reverse("auth-me"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["active_business"] == str(business.id)


def test_active_endpoint_requires_authentication(api_client):
    assert api_client.get(ACTIVE_URL).status_code == status.HTTP_401_UNAUTHORIZED
