"""
Tenant isolation.

These are the tests that matter most in the whole backend: no user may read or
modify another business's records by supplying its ID.
"""

import pytest
from django.urls import reverse
from rest_framework import status

pytestmark = pytest.mark.django_db


def detail_url(business):
    return reverse("business-detail", args=[business.id])


def members_url(business):
    return reverse("business-members", args=[business.id])


def test_cannot_retrieve_another_users_business(authenticated_client, other_business):
    response = authenticated_client.get(detail_url(other_business))

    # 404 rather than 403: a foreign business should not be confirmed to exist.
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cannot_update_another_users_business(authenticated_client, other_business):
    response = authenticated_client.patch(
        detail_url(other_business), {"name": "Hijacked"}, format="json"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    other_business.refresh_from_db()
    assert other_business.name == "Rival Stores"


def test_cannot_archive_another_users_business(authenticated_client, other_business):
    response = authenticated_client.delete(detail_url(other_business))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    other_business.refresh_from_db()
    assert other_business.is_active is True


def test_cannot_read_members_of_another_users_business(authenticated_client, other_business):
    response = authenticated_client.get(members_url(other_business))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cannot_add_themselves_to_another_users_business(
    authenticated_client, other_business, user
):
    response = authenticated_client.post(
        members_url(other_business), {"email": user.email}, format="json"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert other_business.is_member(user) is False


def test_cannot_activate_another_users_business(authenticated_client, other_business, user):
    response = authenticated_client.post(reverse("business-activate", args=[other_business.id]))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    user.refresh_from_db()
    assert user.active_business_id is None


def test_member_of_one_business_cannot_reach_a_sibling_business(
    client_for, business_factory, user, other_user
):
    """A user with their own business still cannot reach an unrelated one."""
    unrelated = business_factory(other_user, name="Unrelated Traders")
    business_factory(user, name="Own Shop")

    response = client_for(user).get(detail_url(unrelated))

    assert response.status_code == status.HTTP_404_NOT_FOUND
