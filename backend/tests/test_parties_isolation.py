"""Parties are the first business-scoped records, so isolation is retested here."""

import pytest
from django.urls import reverse
from rest_framework import status

from apps.parties.models import Party

pytestmark = pytest.mark.django_db

LIST_URL = reverse("party-list")


def detail_url(party):
    return reverse("party-detail", args=[party.id])


@pytest.fixture
def rival_party(other_business, other_user):
    return Party.objects.create(business=other_business, name="Rival Customer")


def test_cannot_list_parties_of_another_business(authenticated_client, rival_party, business):
    response = authenticated_client.get(LIST_URL, {"business": str(rival_party.business_id)})

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cannot_retrieve_a_party_from_another_business(
    authenticated_client, rival_party, business
):
    response = authenticated_client.get(detail_url(rival_party))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cannot_update_a_party_from_another_business(
    authenticated_client, rival_party, business
):
    response = authenticated_client.patch(
        detail_url(rival_party), {"name": "Hijacked"}, format="json"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    rival_party.refresh_from_db()
    assert rival_party.name == "Rival Customer"


def test_cannot_archive_a_party_from_another_business(
    authenticated_client, rival_party, business
):
    response = authenticated_client.delete(detail_url(rival_party))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    rival_party.refresh_from_db()
    assert rival_party.is_active is True


def test_cannot_create_a_party_in_another_business(authenticated_client, other_business):
    response = authenticated_client.post(
        LIST_URL,
        {"name": "Planted", "business": str(other_business.id)},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Party.objects.filter(business=other_business).count() == 0


def test_a_malformed_business_id_is_rejected(authenticated_client, business):
    response = authenticated_client.get(LIST_URL, {"business": "not-a-uuid"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_anonymous_access_is_rejected(api_client, business):
    assert api_client.get(LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED


def test_a_member_can_manage_parties(client_for, business, other_user):
    """Staff need to add customers, so membership is enough — ownership is not required."""
    from apps.businesses.models import Membership, MembershipRole

    Membership.objects.create(business=business, user=other_user, role=MembershipRole.MEMBER)
    other_user.active_business = business
    other_user.save(update_fields=["active_business"])

    response = client_for(other_user).post(LIST_URL, {"name": "Added By Member"}, format="json")

    assert response.status_code == status.HTTP_201_CREATED
