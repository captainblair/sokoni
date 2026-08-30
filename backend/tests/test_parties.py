import pytest
from django.urls import reverse
from rest_framework import status

from apps.parties.models import Party, PartyType

pytestmark = pytest.mark.django_db

LIST_URL = reverse("party-list")


def detail_url(party):
    return reverse("party-detail", args=[party.id])


def create_party(client, name="Mary Wanjiku", **extra):
    payload = {"name": name}
    payload.update(extra)
    return client.post(LIST_URL, payload, format="json")


def test_create_party_uses_the_active_business(authenticated_client, business):
    response = create_party(authenticated_client, phone_number="+254712345678")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["business"] == str(business.id)
    assert response.data["party_type"] == PartyType.CUSTOMER


def test_create_party_accepts_an_explicit_business(
    authenticated_client, business_factory, user
):
    second = business_factory(user, name="Second Shop")

    response = create_party(authenticated_client, business=str(second.id))

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["business"] == str(second.id)


def test_create_party_requires_a_business(authenticated_client):
    response = create_party(authenticated_client)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "business" in response.data


def test_create_supplier(authenticated_client, business):
    response = create_party(
        authenticated_client, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )

    assert response.status_code == status.HTTP_201_CREATED
    party = Party.objects.get(id=response.data["id"])
    assert party.is_supplier
    assert not party.is_customer


def test_a_party_can_be_both_customer_and_supplier(authenticated_client, business):
    response = create_party(authenticated_client, name="Otieno", party_type=PartyType.BOTH)

    party = Party.objects.get(id=response.data["id"])
    assert party.is_customer
    assert party.is_supplier


def test_duplicate_names_are_rejected_case_insensitively(authenticated_client, business):
    create_party(authenticated_client, name="Mary Wanjiku")

    response = create_party(authenticated_client, name="mary wanjiku")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "name" in response.data
    assert Party.objects.filter(business=business).count() == 1


def test_the_same_name_is_allowed_in_a_different_business(
    authenticated_client, business, business_factory, user
):
    second = business_factory(user, name="Second Shop")
    create_party(authenticated_client, name="Mary Wanjiku")

    response = create_party(authenticated_client, name="Mary Wanjiku", business=str(second.id))

    assert response.status_code == status.HTTP_201_CREATED


def test_names_are_trimmed(authenticated_client, business):
    response = create_party(authenticated_client, name="  Mary Wanjiku  ")

    assert response.data["name"] == "Mary Wanjiku"


def test_blank_name_is_rejected(authenticated_client, business):
    response = create_party(authenticated_client, name="   ")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_invalid_phone_number_is_rejected(authenticated_client, business):
    response = create_party(authenticated_client, phone_number="not-a-number")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "phone_number" in response.data


def test_list_returns_only_the_selected_business(
    authenticated_client, business, business_factory, user
):
    second = business_factory(user, name="Second Shop")
    create_party(authenticated_client, name="In First")
    create_party(authenticated_client, name="In Second", business=str(second.id))

    response = authenticated_client.get(LIST_URL)

    assert [item["name"] for item in response.data] == ["In First"]


def test_list_can_target_another_business_you_belong_to(
    authenticated_client, business, business_factory, user
):
    second = business_factory(user, name="Second Shop")
    create_party(authenticated_client, name="In Second", business=str(second.id))

    response = authenticated_client.get(LIST_URL, {"business": str(second.id)})

    assert [item["name"] for item in response.data] == ["In Second"]


def test_type_filter_includes_dual_role_parties(authenticated_client, business):
    create_party(authenticated_client, name="Only Customer", party_type=PartyType.CUSTOMER)
    create_party(authenticated_client, name="Only Supplier", party_type=PartyType.SUPPLIER)
    create_party(authenticated_client, name="Both Roles", party_type=PartyType.BOTH)

    customers = authenticated_client.get(LIST_URL, {"type": "customer"})
    suppliers = authenticated_client.get(LIST_URL, {"type": "supplier"})

    assert {item["name"] for item in customers.data} == {"Only Customer", "Both Roles"}
    assert {item["name"] for item in suppliers.data} == {"Only Supplier", "Both Roles"}


def test_search_matches_name_fragments(authenticated_client, business):
    create_party(authenticated_client, name="Mary Wanjiku")
    create_party(authenticated_client, name="John Otieno")

    response = authenticated_client.get(LIST_URL, {"search": "wanj"})

    assert [item["name"] for item in response.data] == ["Mary Wanjiku"]


def test_update_party(authenticated_client, business):
    created = create_party(authenticated_client)
    party = Party.objects.get(id=created.data["id"])

    response = authenticated_client.patch(
        detail_url(party), {"notes": "Pays on Fridays"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    party.refresh_from_db()
    assert party.notes == "Pays on Fridays"


def test_renaming_to_an_existing_name_is_rejected(authenticated_client, business):
    create_party(authenticated_client, name="Mary Wanjiku")
    second = create_party(authenticated_client, name="John Otieno")
    party = Party.objects.get(id=second.data["id"])

    response = authenticated_client.patch(
        detail_url(party), {"name": "Mary Wanjiku"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_a_party_can_keep_its_own_name_on_update(authenticated_client, business):
    created = create_party(authenticated_client, name="Mary Wanjiku")
    party = Party.objects.get(id=created.data["id"])

    response = authenticated_client.patch(
        detail_url(party), {"name": "Mary Wanjiku", "notes": "Regular"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK


def test_a_party_in_a_non_active_business_is_still_reachable_by_id(
    authenticated_client, business, business_factory, user
):
    second = business_factory(user, name="Second Shop")
    created = create_party(authenticated_client, name="In Second", business=str(second.id))
    party = Party.objects.get(id=created.data["id"])

    response = authenticated_client.get(detail_url(party))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["business"] == str(second.id)


def test_delete_archives_the_party(authenticated_client, business):
    created = create_party(authenticated_client)
    party = Party.objects.get(id=created.data["id"])

    response = authenticated_client.delete(detail_url(party))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    party.refresh_from_db()
    assert party.is_active is False
    assert authenticated_client.get(LIST_URL).data == []


def test_archived_parties_can_be_listed_explicitly(authenticated_client, business):
    created = create_party(authenticated_client)
    authenticated_client.delete(detail_url(Party.objects.get(id=created.data["id"])))

    response = authenticated_client.get(LIST_URL, {"include_archived": "true"})

    assert len(response.data) == 1
