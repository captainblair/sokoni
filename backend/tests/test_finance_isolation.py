"""Financial reports must only ever describe one business."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.businesses.models import Membership, MembershipRole
from apps.debts.models import DebtType
from apps.debts.services import create_debt
from apps.ledger.models import TransactionType
from apps.ledger.services import record_transaction
from apps.parties.models import Party

pytestmark = pytest.mark.django_db

ENDPOINTS = [
    reverse("cash-position"),
    reverse("finance-summary"),
    reverse("float-risk"),
    reverse("daily-brief"),
]


@pytest.fixture
def rival_trade(other_business, other_user):
    record_transaction(
        business=other_business,
        created_by=other_user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("50000.00"),
    )
    create_debt(
        business=other_business,
        created_by=other_user,
        debt_type=DebtType.RECEIVABLE,
        party=Party.objects.create(business=other_business, name="Rival Customer"),
        original_amount=Decimal("9000.00"),
    )


@pytest.mark.parametrize("url", ENDPOINTS)
def test_another_businesss_money_never_appears(
    authenticated_client, business, rival_trade, url
):
    response = authenticated_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert "50000" not in str(response.data)
    assert "9000" not in str(response.data)


@pytest.mark.parametrize("url", ENDPOINTS)
def test_a_foreign_business_id_is_not_found(
    authenticated_client, business, other_business, url
):
    response = authenticated_client.get(url, {"business": str(other_business.id)})

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("url", ENDPOINTS)
def test_reports_require_authentication(api_client, url):
    assert api_client.get(url).status_code == status.HTTP_401_UNAUTHORIZED


def test_a_member_can_read_the_businesss_figures(
    client_for, business, other_user, user
):
    Membership.objects.create(
        business=business, user=other_user, role=MembershipRole.MEMBER
    )
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("2400.00"),
    )

    response = client_for(other_user).get(
        reverse("cash-position"), {"business": str(business.id)}
    )

    assert response.status_code == status.HTTP_200_OK
    assert Decimal(response.data["available_cash"]) == Decimal("2400.00")


def test_a_user_without_an_active_business_is_told_so(client_for, user_factory):
    stranger = user_factory(email="nobody@example.com")

    response = client_for(stranger).get(reverse("cash-position"))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "business" in response.data
