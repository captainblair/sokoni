import pytest
from django.urls import reverse
from rest_framework import status

from apps.businesses.models import MembershipRole

pytestmark = pytest.mark.django_db


def members_url(business):
    return reverse("business-members", args=[business.id])


def member_url(business, membership):
    return reverse("business-manage-member", args=[business.id, membership.id])


def detail_url(business):
    return reverse("business-detail", args=[business.id])


def add_member(client, business, email, role=MembershipRole.MEMBER):
    return client.post(members_url(business), {"email": email, "role": role}, format="json")


def test_owner_can_add_an_existing_account_as_member(authenticated_client, business, other_user):
    response = add_member(authenticated_client, business, other_user.email)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["email"] == other_user.email
    assert response.data["role"] == MembershipRole.MEMBER
    assert business.is_member(other_user)


def test_adding_an_unknown_email_is_rejected(authenticated_client, business):
    response = add_member(authenticated_client, business, "nobody@example.com")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


def test_adding_the_same_user_twice_is_rejected(authenticated_client, business, other_user):
    add_member(authenticated_client, business, other_user.email)

    response = add_member(authenticated_client, business, other_user.email)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert business.memberships.filter(user=other_user).count() == 1


def test_members_list_includes_every_member(authenticated_client, business, other_user):
    add_member(authenticated_client, business, other_user.email)

    response = authenticated_client.get(members_url(business))

    assert response.status_code == status.HTTP_200_OK
    assert {item["email"] for item in response.data} == {
        "trader@example.com",
        other_user.email,
    }


def test_member_can_read_but_not_modify_the_business(
    authenticated_client, client_for, business, other_user
):
    add_member(authenticated_client, business, other_user.email)
    member_client = client_for(other_user)

    assert member_client.get(detail_url(business)).status_code == status.HTTP_200_OK

    update = member_client.patch(detail_url(business), {"name": "Renamed"}, format="json")
    assert update.status_code == status.HTTP_403_FORBIDDEN

    delete = member_client.delete(detail_url(business))
    assert delete.status_code == status.HTTP_403_FORBIDDEN


def test_member_cannot_add_other_members(
    authenticated_client, client_for, business, other_user, user_factory
):
    add_member(authenticated_client, business, other_user.email)
    third = user_factory(email="third@example.com")

    response = add_member(client_for(other_user), business, third.email)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert business.is_member(third) is False


def test_owner_can_promote_a_member(authenticated_client, business, other_user):
    add_member(authenticated_client, business, other_user.email)
    membership = business.memberships.get(user=other_user)

    response = authenticated_client.patch(
        member_url(business, membership), {"role": MembershipRole.OWNER}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    membership.refresh_from_db()
    assert membership.role == MembershipRole.OWNER


def test_owner_can_remove_a_member(authenticated_client, business, other_user):
    add_member(authenticated_client, business, other_user.email)
    membership = business.memberships.get(user=other_user)

    response = authenticated_client.delete(member_url(business, membership))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert business.is_member(other_user) is False


def test_the_last_owner_cannot_be_removed(authenticated_client, business, user):
    membership = business.memberships.get(user=user)

    response = authenticated_client.delete(member_url(business, membership))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert business.is_owner(user)


def test_the_last_owner_cannot_be_demoted(authenticated_client, business, user):
    membership = business.memberships.get(user=user)

    response = authenticated_client.patch(
        member_url(business, membership), {"role": MembershipRole.MEMBER}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    membership.refresh_from_db()
    assert membership.role == MembershipRole.OWNER


def test_an_owner_can_be_removed_once_another_owner_exists(
    authenticated_client, business, other_user, user
):
    add_member(authenticated_client, business, other_user.email, role=MembershipRole.OWNER)
    membership = business.memberships.get(user=user)

    response = authenticated_client.delete(member_url(business, membership))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert business.is_member(user) is False
    assert business.is_owner(other_user)


def test_removing_a_member_clears_their_active_business(
    authenticated_client, client_for, business, other_user
):
    add_member(authenticated_client, business, other_user.email)
    client_for(other_user).post(reverse("business-activate", args=[business.id]))

    other_user.refresh_from_db()
    assert other_user.active_business_id == business.id

    membership = business.memberships.get(user=other_user)
    authenticated_client.delete(member_url(business, membership))

    other_user.refresh_from_db()
    assert other_user.active_business_id is None
