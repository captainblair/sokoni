"""Cash in hand, and what is still owed in each direction."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.debts.models import DebtType
from apps.debts.services import create_debt, record_payment
from apps.ledger.models import PaymentStatus, Transaction, TransactionType
from apps.ledger.services import record_transaction
from apps.parties.models import Party, PartyType

pytestmark = pytest.mark.django_db

URL = reverse("cash-position")


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def supplier(business):
    return Party.objects.create(
        business=business, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )


def sale(business, user, **overrides):
    fields = {"transaction_type": TransactionType.SALE, "amount": Decimal("2400.00")}
    fields.update(overrides)
    return record_transaction(business=business, created_by=user, **fields)


def position(client, **params):
    response = client.get(URL, params)
    assert response.status_code == status.HTTP_200_OK
    return response.data


def test_paid_sales_and_expenses_net_out(authenticated_client, business, user):
    sale(business, user)
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("500.00"),
    )

    data = position(authenticated_client)

    assert Decimal(data["available_cash"]) == Decimal("1900.00")
    assert Decimal(data["cash_in"]) == Decimal("2400.00")
    assert Decimal(data["cash_out"]) == Decimal("500.00")
    assert data["currency"] == "KES"


def test_a_credit_sale_is_owed_not_held(authenticated_client, business, user, customer):
    sale(business, user, payment_status=PaymentStatus.CREDIT, party=customer)

    data = position(authenticated_client)

    assert Decimal(data["available_cash"]) == Decimal("0.00")
    assert Decimal(data["receivables"]) == Decimal("2400.00")
    assert Decimal(data["projected_cash"]) == Decimal("2400.00")


def test_paying_a_tracked_debt_is_counted_once(
    authenticated_client, business, user, customer
):
    txn = sale(
        business,
        user,
        amount=Decimal("800.00"),
        payment_status=PaymentStatus.CREDIT,
        party=customer,
    )
    record_payment(txn.debt, amount=Decimal("300.00"))

    data = position(authenticated_client)

    # 300 arrived once, even though both the debt and the transaction record it.
    assert Decimal(data["available_cash"]) == Decimal("300.00")
    assert Decimal(data["receivables"]) == Decimal("500.00")


def test_payments_on_a_standalone_debt_move_cash(
    authenticated_client, business, user, customer
):
    debt = create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("2000.00"),
    )
    record_payment(debt, amount=Decimal("500.00"))

    data = position(authenticated_client)

    assert Decimal(data["available_cash"]) == Decimal("500.00")
    assert Decimal(data["receivables"]) == Decimal("1500.00")


def test_paying_a_supplier_debt_reduces_cash(
    authenticated_client, business, user, supplier
):
    sale(business, user)
    debt = create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.PAYABLE,
        party=supplier,
        original_amount=Decimal("800.00"),
    )
    record_payment(debt, amount=Decimal("800.00"))

    data = position(authenticated_client)

    assert Decimal(data["available_cash"]) == Decimal("1600.00")
    assert Decimal(data["payables"]) == Decimal("0.00")


def test_credit_sale_without_a_party_still_counts_as_owed(
    authenticated_client, business, user
):
    Transaction.objects.create(
        business=business,
        transaction_type=TransactionType.SALE,
        amount=Decimal("600.00"),
        amount_paid=Decimal("0.00"),
        payment_status=PaymentStatus.CREDIT,
    )

    data = position(authenticated_client)

    assert Decimal(data["receivables"]) == Decimal("600.00")
    assert Decimal(data["available_cash"]) == Decimal("0.00")


def test_payables_are_reported_separately(
    authenticated_client, business, user, supplier
):
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.PURCHASE,
        amount=Decimal("800.00"),
        payment_status=PaymentStatus.CREDIT,
        party=supplier,
    )

    data = position(authenticated_client)

    assert Decimal(data["payables"]) == Decimal("800.00")
    assert Decimal(data["receivables"]) == Decimal("0.00")
    assert Decimal(data["projected_cash"]) == Decimal("-800.00")


def test_archiving_a_debt_leaves_the_transaction_balance_visible(
    authenticated_client, business, user, customer
):
    txn = sale(
        business,
        user,
        amount=Decimal("800.00"),
        payment_status=PaymentStatus.CREDIT,
        party=customer,
    )
    txn.debt.archive()

    data = position(authenticated_client)

    assert Decimal(data["receivables"]) == Decimal("800.00")


def test_archived_transactions_are_excluded(authenticated_client, business, user):
    txn = sale(business, user)
    txn.archive()

    assert Decimal(position(authenticated_client)["available_cash"]) == Decimal("0.00")


def test_an_empty_business_reports_zero(authenticated_client, business):
    data = position(authenticated_client)

    assert Decimal(data["available_cash"]) == Decimal("0.00")
    assert Decimal(data["receivables"]) == Decimal("0.00")
    assert Decimal(data["payables"]) == Decimal("0.00")


def test_overdue_debts_are_flagged(authenticated_client, business, user, customer):
    from datetime import timedelta

    from django.utils import timezone

    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("400.00"),
        due_date=timezone.localdate() - timedelta(days=5),
    )

    data = position(authenticated_client)

    assert Decimal(data["receivables_overdue"]) == Decimal("400.00")
