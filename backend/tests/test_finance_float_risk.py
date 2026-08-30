"""Whether the business can meet what falls due soon."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.debts.models import DebtType
from apps.debts.services import create_debt
from apps.ledger.models import TransactionType
from apps.ledger.services import record_transaction
from apps.parties.models import Party, PartyType

pytestmark = pytest.mark.django_db

URL = reverse("float-risk")


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def supplier(business):
    return Party.objects.create(
        business=business, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )


def hold(business, user, amount):
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal(amount),
    )


def owe(business, user, party, amount, due_in_days=3, debt_type=DebtType.PAYABLE):
    return create_debt(
        business=business,
        created_by=user,
        debt_type=debt_type,
        party=party,
        original_amount=Decimal(amount),
        due_date=timezone.localdate() + timedelta(days=due_in_days),
    )


def risk(client, **params):
    response = client.get(URL, params)
    assert response.status_code == status.HTTP_200_OK
    return response.data


def test_nothing_due_is_no_risk(authenticated_client, business, user):
    hold(business, user, "5000.00")

    data = risk(authenticated_client)

    assert data["risk_level"] == "none"
    assert Decimal(data["obligations_due"]) == Decimal("0.00")


def test_covered_obligations_are_no_risk(
    authenticated_client, business, user, supplier
):
    hold(business, user, "5000.00")
    owe(business, user, supplier, "2000.00")

    data = risk(authenticated_client)

    assert data["risk_level"] == "none"
    assert Decimal(data["shortfall"]) == Decimal("0.00")
    assert Decimal(data["projected_balance"]) == Decimal("3000.00")


def test_shortfall_covered_only_by_receivables_is_a_watch(
    authenticated_client, business, user, supplier, customer
):
    hold(business, user, "1000.00")
    owe(business, user, supplier, "2500.00")
    owe(business, user, customer, "3000.00", debt_type=DebtType.RECEIVABLE)

    data = risk(authenticated_client)

    assert data["risk_level"] == "watch"
    assert Decimal(data["shortfall"]) == Decimal("1500.00")
    assert Decimal(data["expected_receipts"]) == Decimal("3000.00")


def test_shortfall_beyond_receivables_is_high_risk(
    authenticated_client, business, user, supplier, customer
):
    hold(business, user, "1000.00")
    owe(business, user, supplier, "6000.00")
    owe(business, user, customer, "500.00", debt_type=DebtType.RECEIVABLE)

    data = risk(authenticated_client)

    assert data["risk_level"] == "high"
    assert Decimal(data["shortfall"]) == Decimal("5000.00")


def test_obligations_beyond_the_horizon_are_not_counted(
    authenticated_client, business, user, supplier
):
    hold(business, user, "1000.00")
    owe(business, user, supplier, "9000.00", due_in_days=30)

    data = risk(authenticated_client)

    assert Decimal(data["obligations_due"]) == Decimal("0.00")
    assert data["risk_level"] == "none"


def test_the_horizon_can_be_widened(authenticated_client, business, user, supplier):
    hold(business, user, "1000.00")
    owe(business, user, supplier, "9000.00", due_in_days=30)

    data = risk(authenticated_client, days=60)

    assert data["horizon_days"] == 60
    assert Decimal(data["obligations_due"]) == Decimal("9000.00")
    assert data["risk_level"] == "high"


def test_overdue_obligations_are_always_due(
    authenticated_client, business, user, supplier
):
    hold(business, user, "1000.00")
    owe(business, user, supplier, "400.00", due_in_days=-10)

    data = risk(authenticated_client)

    assert Decimal(data["obligations_due"]) == Decimal("400.00")
    assert Decimal(data["overdue_payables"]) == Decimal("400.00")


def test_debts_without_a_due_date_are_reported_separately(
    authenticated_client, business, user, supplier
):
    hold(business, user, "1000.00")
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.PAYABLE,
        party=supplier,
        original_amount=Decimal("700.00"),
    )

    data = risk(authenticated_client)

    assert Decimal(data["undated_payables"]) == Decimal("700.00")
    assert Decimal(data["obligations_due"]) == Decimal("0.00")


def test_undated_receivables_are_not_counted_as_expected_receipts(
    authenticated_client, business, user, customer
):
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("4200.00"),
    )

    data = risk(authenticated_client)

    # Nobody promised a date, so nobody can plan around it.
    assert Decimal(data["expected_receipts"]) == Decimal("0.00")
    assert Decimal(data["undated_receivables"]) == Decimal("4200.00")


def test_settled_debts_stop_counting(authenticated_client, business, user, supplier):
    from apps.debts.services import record_payment

    hold(business, user, "5000.00")
    debt = owe(business, user, supplier, "2000.00")
    record_payment(debt, amount=Decimal("2000.00"))

    data = risk(authenticated_client)

    assert Decimal(data["obligations_due"]) == Decimal("0.00")
    assert Decimal(data["available_cash"]) == Decimal("3000.00")


def test_invalid_horizon_is_rejected(authenticated_client, business):
    assert (
        authenticated_client.get(URL, {"days": "0"}).status_code
        == status.HTTP_400_BAD_REQUEST
    )
    assert (
        authenticated_client.get(URL, {"days": "soon"}).status_code
        == status.HTTP_400_BAD_REQUEST
    )
