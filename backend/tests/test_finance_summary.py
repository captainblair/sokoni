"""Revenue, costs and cash movement over a period."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.ledger.models import (
    PaymentMethod,
    PaymentStatus,
    Transaction,
    TransactionType,
)
from apps.parties.models import Party

pytestmark = pytest.mark.django_db

URL = reverse("finance-summary")


@pytest.fixture
def trading(business):
    now = timezone.now()
    Transaction.objects.create(
        business=business,
        transaction_type=TransactionType.SALE,
        amount=Decimal("2400.00"),
        amount_paid=Decimal("2400.00"),
        payment_method=PaymentMethod.MPESA,
        occurred_at=now,
    )
    Transaction.objects.create(
        business=business,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("500.00"),
        amount_paid=Decimal("500.00"),
        occurred_at=now,
    )
    Transaction.objects.create(
        business=business,
        transaction_type=TransactionType.SALE,
        amount=Decimal("1000.00"),
        amount_paid=Decimal("0.00"),
        payment_status=PaymentStatus.CREDIT,
        occurred_at=now,
    )
    Transaction.objects.create(
        business=business,
        transaction_type=TransactionType.SALE,
        amount=Decimal("700.00"),
        amount_paid=Decimal("700.00"),
        occurred_at=now - timedelta(days=40),
    )


def summary(client, **params):
    response = client.get(URL, params)
    assert response.status_code == status.HTTP_200_OK
    return response.data


def test_todays_revenue_and_expenses(authenticated_client, trading):
    data = summary(authenticated_client)

    assert data["period"] == "today"
    assert Decimal(data["revenue"]) == Decimal("3400.00")
    assert Decimal(data["expenses"]) == Decimal("500.00")
    assert data["transaction_count"] == 3


def test_profit_is_revenue_less_costs_on_an_accrual_basis(
    authenticated_client, trading
):
    data = summary(authenticated_client)

    # The 1,000 credit sale is earned today even though no cash arrived.
    assert Decimal(data["profit_estimate"]) == Decimal("2900.00")


def test_cash_flow_counts_only_money_that_moved(authenticated_client, trading):
    data = summary(authenticated_client)

    assert Decimal(data["cash_in"]) == Decimal("2400.00")
    assert Decimal(data["cash_out"]) == Decimal("500.00")
    assert Decimal(data["net_cash_flow"]) == Decimal("1900.00")


def test_credit_given_is_reported(authenticated_client, trading):
    data = summary(authenticated_client)

    assert Decimal(data["credit_given"]) == Decimal("1000.00")
    assert Decimal(data["credit_taken"]) == Decimal("0.00")


def test_older_entries_are_outside_todays_window(authenticated_client, trading):
    today = summary(authenticated_client)
    everything = summary(authenticated_client, period="all")

    assert Decimal(today["revenue"]) == Decimal("3400.00")
    assert Decimal(everything["revenue"]) == Decimal("4100.00")


def test_month_covers_the_calendar_month_so_far(authenticated_client, trading):
    data = summary(authenticated_client, period="month")

    assert data["date_from"] == timezone.localdate().replace(day=1).isoformat()
    assert data["date_to"] == timezone.localdate().isoformat()


def test_week_covers_the_last_seven_days(authenticated_client, trading):
    data = summary(authenticated_client, period="week")

    assert data["date_from"] == (timezone.localdate() - timedelta(days=6)).isoformat()


def test_explicit_date_range(authenticated_client, trading):
    day = (timezone.localdate() - timedelta(days=40)).isoformat()
    data = summary(authenticated_client, date_from=day, date_to=day)

    assert data["period"] == "custom"
    assert Decimal(data["revenue"]) == Decimal("700.00")


def test_reversed_date_range_is_rejected(authenticated_client, business):
    response = authenticated_client.get(
        URL, {"date_from": "2026-05-10", "date_to": "2026-05-01"}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_unknown_period_is_rejected(authenticated_client, business):
    response = authenticated_client.get(URL, {"period": "fortnight"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_malformed_date_is_rejected(authenticated_client, business):
    response = authenticated_client.get(URL, {"date_from": "last tuesday"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_breakdown_by_type_and_method(authenticated_client, trading):
    data = summary(authenticated_client)

    by_type = {row["key"]: Decimal(row["total"]) for row in data["by_type"]}
    assert by_type[TransactionType.SALE] == Decimal("3400.00")
    assert by_type[TransactionType.EXPENSE] == Decimal("500.00")

    by_method = {row["key"]: Decimal(row["total"]) for row in data["by_payment_method"]}
    assert by_method[PaymentMethod.MPESA] == Decimal("2400.00")
    # The 1,000 credit sale settled nothing, so it belongs to no method yet.
    assert by_method[PaymentMethod.CASH] == Decimal("500.00")


def test_a_quiet_day_reports_zeroes(authenticated_client, business):
    data = summary(authenticated_client)

    assert Decimal(data["revenue"]) == Decimal("0.00")
    assert Decimal(data["profit_estimate"]) == Decimal("0.00")
    assert data["transaction_count"] == 0
    assert data["by_type"] == []


def test_standalone_debt_payments_count_as_cash_in(
    authenticated_client, business, user
):
    from apps.debts.models import DebtType
    from apps.debts.services import create_debt, record_payment

    party = Party.objects.create(business=business, name="Mary Wanjiku")
    debt = create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=party,
        original_amount=Decimal("900.00"),
    )
    record_payment(debt, amount=Decimal("400.00"))

    data = summary(authenticated_client)

    assert Decimal(data["cash_in"]) == Decimal("400.00")
    # An old debt being settled is not new revenue.
    assert Decimal(data["revenue"]) == Decimal("0.00")
