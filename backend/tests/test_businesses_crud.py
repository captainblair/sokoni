import pytest
from django.urls import reverse
from rest_framework import status

from apps.businesses.models import Business, MembershipRole

pytestmark = pytest.mark.django_db

LIST_URL = reverse("business-list")


def detail_url(business):
    return reverse("business-detail", args=[business.id])


def test_create_business_makes_creator_the_owner(authenticated_client, user):
    response = authenticated_client.post(
        LIST_URL,
        {"name": "Amina Groceries", "business_type": "retail", "location": "Gikomba"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["name"] == "Amina Groceries"
    assert response.data["my_role"] == MembershipRole.OWNER
    assert response.data["member_count"] == 1

    business = Business.objects.get(id=response.data["id"])
    assert business.is_owner(user)
    assert business.created_by == user


def test_first_business_becomes_the_active_business(authenticated_client, user):
    response = authenticated_client.post(LIST_URL, {"name": "First Shop"}, format="json")

    user.refresh_from_db()
    assert str(user.active_business_id) == response.data["id"]


def test_second_business_does_not_replace_active_business(authenticated_client, user):
    first = authenticated_client.post(LIST_URL, {"name": "First Shop"}, format="json")
    authenticated_client.post(LIST_URL, {"name": "Second Shop"}, format="json")

    user.refresh_from_db()
    assert str(user.active_business_id) == first.data["id"]


def test_currency_defaults_to_kes(authenticated_client):
    response = authenticated_client.post(LIST_URL, {"name": "Shop"}, format="json")

    assert response.data["currency"] == "KES"


def test_create_requires_a_name(authenticated_client):
    response = authenticated_client.post(LIST_URL, {"location": "Gikomba"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in response.data


def test_list_returns_only_own_businesses(authenticated_client, business, other_business):
    response = authenticated_client.get(LIST_URL)

    assert response.status_code == status.HTTP_200_OK
    returned = [item["id"] for item in response.data]
    assert str(business.id) in returned
    assert str(other_business.id) not in returned


def test_retrieve_own_business(authenticated_client, business):
    response = authenticated_client.get(detail_url(business))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == str(business.id)


def test_owner_can_update_business(authenticated_client, business):
    response = authenticated_client.patch(
        detail_url(business), {"location": "Kariobangi"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    business.refresh_from_db()
    assert business.location == "Kariobangi"


def test_destroy_archives_instead_of_deleting(authenticated_client, business, user):
    response = authenticated_client.delete(detail_url(business))

    assert response.status_code == status.HTTP_204_NO_CONTENT

    business.refresh_from_db()
    assert business.is_active is False
    assert Business.objects.filter(id=business.id).exists()

    user.refresh_from_db()
    assert user.active_business_id is None


def test_archived_business_disappears_from_list(authenticated_client, business):
    authenticated_client.delete(detail_url(business))

    response = authenticated_client.get(LIST_URL)

    assert response.data == []


def test_anonymous_access_is_rejected(api_client, business):
    assert api_client.get(LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED
    assert api_client.get(detail_url(business)).status_code == status.HTTP_401_UNAUTHORIZED
