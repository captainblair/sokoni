"""The agent is another door into the same books, and the same wall around them."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.businesses.models import Membership, MembershipRole
from apps.ledger.models import Transaction, TransactionType
from apps.ledger.services import record_transaction
from apps.parties.models import Party

pytestmark = pytest.mark.django_db

URL = reverse("agent-execute")
REGISTRY = reverse("agent-tools")


@pytest.fixture
def rival_trade(other_business, other_user):
    Party.objects.create(business=other_business, name="Rival Customer")
    record_transaction(
        business=other_business,
        created_by=other_user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("50000.00"),
    )


def call(client, tool, parameters=None, **extra):
    payload = {"tool": tool, "parameters": parameters or {}}
    payload.update(extra)
    return client.post(URL, payload, format="json")


def test_a_question_never_sees_another_businesss_money(
    authenticated_client, business, rival_trade
):
    response = call(authenticated_client, "get_cash_position")

    assert response.status_code == status.HTTP_200_OK
    assert "50000" not in str(response.data)
    assert Decimal(response.data["data"]["available_cash"]) == Decimal("0.00")


def test_a_foreign_business_id_is_not_found(
    authenticated_client, business, other_business
):
    response = call(
        authenticated_client,
        "get_cash_position",
        business=str(other_business.id),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_a_write_cannot_land_in_another_business(
    authenticated_client, business, other_business
):
    response = call(
        authenticated_client,
        "record_sale",
        {"amount": "100.00"},
        business=str(other_business.id),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Transaction.objects.filter(business=other_business).count() == 0
    assert Transaction.objects.filter(business=business).count() == 0


def test_a_name_in_another_business_is_treated_as_unknown(
    authenticated_client, business, rival_trade
):
    response = call(
        authenticated_client,
        "get_party_balance",
        {"party": "Rival Customer"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Party.objects.filter(business=business).count() == 0


def test_a_confirmation_cannot_be_spent_on_another_of_the_users_businesses(
    authenticated_client, business, business_factory, user
):
    other = business_factory(user, name="Amina Hardware")
    token = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.4
    ).data["confirmation"]["token"]

    response = authenticated_client.post(
        URL,
        {
            "tool": "record_sale",
            "confirmation_token": token,
            "business": str(other.id),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0


def test_execution_requires_authentication(api_client, business):
    assert api_client.post(URL, {"tool": "get_cash_position"}).status_code == (
        status.HTTP_401_UNAUTHORIZED
    )


def test_the_registry_requires_authentication(api_client):
    assert api_client.get(REGISTRY).status_code == status.HTTP_401_UNAUTHORIZED


def test_a_member_can_ask_through_the_agent(client_for, business, other_user, user):
    Membership.objects.create(
        business=business, user=other_user, role=MembershipRole.MEMBER
    )
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("2400.00"),
    )

    response = client_for(other_user).post(
        URL,
        {
            "tool": "get_cash_position",
            "parameters": {},
            "business": str(business.id),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert Decimal(response.data["data"]["available_cash"]) == Decimal("2400.00")
