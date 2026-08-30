"""Paying debts down, in instalments, the way informal trade actually works."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.debts.models import Debt, DebtStatus, DebtType
from apps.debts.services import DebtRuleViolation, record_payment
from apps.ledger.models import PaymentMethod
from apps.parties.models import Party

pytestmark = pytest.mark.django_db


def payments_url(debt):
    return reverse("debt-payments", args=[debt.id])


def detail_url(debt):
    return reverse("debt-detail", args=[debt.id])


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def debt(business, customer, user):
    return Debt.objects.create(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("800.00"),
        description="Sugar taken on credit",
    )


def test_a_part_payment_leaves_a_balance(authenticated_client, debt):
    response = authenticated_client.post(
        payments_url(debt),
        {"amount": "300.00", "payment_method": PaymentMethod.MPESA},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    debt.refresh_from_db()
    assert debt.amount_paid == Decimal("300.00")
    assert debt.balance == Decimal("500.00")
    assert debt.status == DebtStatus.PARTIAL


def test_instalments_settle_the_debt(authenticated_client, debt):
    authenticated_client.post(payments_url(debt), {"amount": "500.00"}, format="json")
    authenticated_client.post(payments_url(debt), {"amount": "300.00"}, format="json")

    debt.refresh_from_db()
    assert debt.balance == Decimal("0.00")
    assert debt.status == DebtStatus.SETTLED
    assert debt.is_settled is True


def test_payment_history_is_kept(authenticated_client, debt):
    authenticated_client.post(payments_url(debt), {"amount": "500.00"}, format="json")
    authenticated_client.post(payments_url(debt), {"amount": "300.00"}, format="json")

    response = authenticated_client.get(payments_url(debt))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 2
    assert {Decimal(p["amount"]) for p in response.data} == {
        Decimal("500.00"),
        Decimal("300.00"),
    }


def test_payment_cannot_exceed_the_balance(authenticated_client, debt):
    response = authenticated_client.post(
        payments_url(debt), {"amount": "900.00"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    debt.refresh_from_db()
    assert debt.amount_paid == Decimal("0.00")


def test_payment_must_be_positive(authenticated_client, debt):
    response = authenticated_client.post(
        payments_url(debt), {"amount": "0.00"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_settled_debt_takes_no_further_payment(authenticated_client, debt):
    authenticated_client.post(payments_url(debt), {"amount": "800.00"}, format="json")

    response = authenticated_client.post(
        payments_url(debt), {"amount": "100.00"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_debt_can_be_written_off(authenticated_client, debt):
    response = authenticated_client.post(
        reverse("debt-write-off", args=[debt.id]),
        {"notes": "Customer moved away"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    debt.refresh_from_db()
    assert debt.status == DebtStatus.WRITTEN_OFF
    assert debt.balance == Decimal("0.00")
    assert "Customer moved away" in debt.notes


def test_written_off_debt_takes_no_payment(authenticated_client, debt):
    authenticated_client.post(reverse("debt-write-off", args=[debt.id]), format="json")

    response = authenticated_client.post(
        payments_url(debt), {"amount": "100.00"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_settled_debt_cannot_be_written_off(debt):
    record_payment(debt, amount=Decimal("800.00"))

    with pytest.raises(DebtRuleViolation):
        from apps.debts.services import write_off_debt

        write_off_debt(debt)
