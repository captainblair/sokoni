"""Recording who owes what, and when it is due."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.debts.models import AgingBucket, Debt, DebtStatus, DebtType
from apps.parties.models import Party, PartyType

pytestmark = pytest.mark.django_db

LIST_URL = reverse("debt-list")


def detail_url(debt):
    return reverse("debt-detail", args=[debt.id])


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def supplier(business):
    return Party.objects.create(
        business=business, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )


def create_debt(client, party, **overrides):
    payload = {
        "debt_type": DebtType.RECEIVABLE,
        "party": str(party.id),
        "original_amount": "800.00",
    }
    payload.update(overrides)
    return client.post(LIST_URL, payload, format="json")


def test_record_a_receivable(authenticated_client, business, customer, user):
    response = create_debt(
        authenticated_client, customer, description="Sugar taken on credit"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["debt_type"] == DebtType.RECEIVABLE
    assert Decimal(response.data["balance"]) == Decimal("800.00")
    assert response.data["status"] == DebtStatus.OPEN
    assert response.data["party_name"] == "Mary Wanjiku"
    assert response.data["currency"] == "KES"

    debt = Debt.objects.get(id=response.data["id"])
    assert debt.business == business
    assert debt.created_by == user


def test_record_a_payable(authenticated_client, supplier):
    response = create_debt(
        authenticated_client,
        supplier,
        debt_type=DebtType.PAYABLE,
        original_amount="1200.00",
    )

    assert response.status_code == status.HTTP_201_CREATED
    debt = Debt.objects.get(id=response.data["id"])
    assert debt.debt_type == DebtType.PAYABLE
    assert debt.balance == Decimal("1200.00")


def test_debt_can_carry_a_due_date(authenticated_client, customer):
    due = timezone.localdate() + timedelta(days=7)
    response = create_debt(authenticated_client, customer, due_date=due.isoformat())

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["due_date"] == due.isoformat()
    assert response.data["is_overdue"] is False
    assert response.data["aging_bucket"] == AgingBucket.CURRENT


def test_debt_amount_must_be_positive(authenticated_client, customer):
    response = create_debt(authenticated_client, customer, original_amount="0.00")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "original_amount" in response.data


def test_debt_requires_a_party(authenticated_client, business):
    response = authenticated_client.post(
        LIST_URL,
        {"debt_type": DebtType.RECEIVABLE, "original_amount": "500.00"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "party" in response.data


def test_debt_cannot_reference_another_businesss_party(
    authenticated_client, business, other_business
):
    stranger = Party.objects.create(business=other_business, name="Rival Customer")
    response = create_debt(authenticated_client, stranger)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "party" in response.data


def test_due_date_and_notes_can_be_corrected(authenticated_client, customer):
    debt = Debt.objects.get(id=create_debt(authenticated_client, customer).data["id"])
    due = timezone.localdate() + timedelta(days=3)

    response = authenticated_client.patch(
        detail_url(debt),
        {"due_date": due.isoformat(), "notes": "Promised after market day"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    debt.refresh_from_db()
    assert debt.due_date == due
    assert debt.notes == "Promised after market day"


def test_debt_amount_cannot_drop_below_what_was_paid(authenticated_client, customer):
    debt = Debt.objects.get(id=create_debt(authenticated_client, customer).data["id"])
    authenticated_client.post(
        reverse("debt-payments", args=[debt.id]), {"amount": "500.00"}, format="json"
    )

    response = authenticated_client.patch(
        detail_url(debt), {"original_amount": "300.00"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_archiving_a_debt_keeps_it_out_of_the_default_list(
    authenticated_client, customer
):
    debt = Debt.objects.get(id=create_debt(authenticated_client, customer).data["id"])

    assert (
        authenticated_client.delete(detail_url(debt)).status_code
        == status.HTTP_204_NO_CONTENT
    )

    debt.refresh_from_db()
    assert debt.is_active is False
    assert len(authenticated_client.get(LIST_URL).data) == 0
