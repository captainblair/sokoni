"""One trader's debt book must never leak into another's."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.businesses.models import Membership, MembershipRole
from apps.debts.models import Debt, DebtType
from apps.parties.models import Party

pytestmark = pytest.mark.django_db

LIST_URL = reverse("debt-list")


@pytest.fixture
def rival_debt(other_business):
    party = Party.objects.create(business=other_business, name="Rival Customer")
    return Debt.objects.create(
        business=other_business,
        debt_type=DebtType.RECEIVABLE,
        party=party,
        original_amount=Decimal("5000.00"),
    )


def test_debts_of_another_business_are_not_listed(
    authenticated_client, business, rival_debt
):
    response = authenticated_client.get(LIST_URL)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 0


def test_foreign_debt_is_not_found(authenticated_client, business, rival_debt):
    response = authenticated_client.get(reverse("debt-detail", args=[rival_debt.id]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_foreign_debt_cannot_be_paid(authenticated_client, business, rival_debt):
    response = authenticated_client.post(
        reverse("debt-payments", args=[rival_debt.id]),
        {"amount": "100.00"},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    rival_debt.refresh_from_db()
    assert rival_debt.amount_paid == Decimal("0.00")


def test_foreign_debt_cannot_be_written_off(authenticated_client, business, rival_debt):
    response = authenticated_client.post(
        reverse("debt-write-off", args=[rival_debt.id]), format="json"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_a_member_sees_the_businesss_debts(
    client_for, business, other_user, rival_debt
):
    Membership.objects.create(
        business=business, user=other_user, role=MembershipRole.MEMBER
    )
    party = Party.objects.create(business=business, name="Mary Wanjiku")
    debt = Debt.objects.create(
        business=business,
        debt_type=DebtType.RECEIVABLE,
        party=party,
        original_amount=Decimal("800.00"),
    )

    response = client_for(other_user).get(LIST_URL, {"business": str(business.id)})

    assert response.status_code == status.HTTP_200_OK
    assert {item["id"] for item in response.data} == {str(debt.id)}
