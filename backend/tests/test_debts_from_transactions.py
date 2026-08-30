"""A credit sale or purchase should become a tracked debt without being asked twice."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.debts.models import Debt, DebtStatus, DebtType
from apps.ledger.models import PaymentStatus, Transaction, TransactionType
from apps.parties.models import Party, PartyType

pytestmark = pytest.mark.django_db

TRANSACTIONS_URL = reverse("transaction-list")


def transaction_url(txn):
    return reverse("transaction-detail", args=[txn.id])


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def supplier(business):
    return Party.objects.create(
        business=business, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )


def record(client, **overrides):
    payload = {"transaction_type": TransactionType.SALE, "amount": "2400.00"}
    payload.update(overrides)
    return client.post(TRANSACTIONS_URL, payload, format="json")


def test_credit_sale_creates_a_receivable(authenticated_client, customer):
    response = record(
        authenticated_client,
        amount="800.00",
        payment_status=PaymentStatus.CREDIT,
        party=str(customer.id),
    )

    assert response.status_code == status.HTTP_201_CREATED
    debt = Debt.objects.get(source_transaction_id=response.data["id"])
    assert debt.debt_type == DebtType.RECEIVABLE
    assert debt.party == customer
    assert debt.balance == Decimal("800.00")
    assert debt.status == DebtStatus.OPEN


def test_credit_purchase_creates_a_payable(authenticated_client, supplier):
    response = record(
        authenticated_client,
        transaction_type=TransactionType.PURCHASE,
        amount="800.00",
        payment_status=PaymentStatus.CREDIT,
        party=str(supplier.id),
    )

    debt = Debt.objects.get(source_transaction_id=response.data["id"])
    assert debt.debt_type == DebtType.PAYABLE
    assert debt.balance == Decimal("800.00")


def test_partial_payment_at_sale_time_creates_a_partial_debt(
    authenticated_client, customer
):
    response = record(
        authenticated_client,
        amount="1000.00",
        amount_paid="400.00",
        party=str(customer.id),
    )

    debt = Debt.objects.get(source_transaction_id=response.data["id"])
    assert debt.status == DebtStatus.PARTIAL
    assert debt.balance == Decimal("600.00")


def test_paid_sale_creates_no_debt(authenticated_client, customer):
    response = record(authenticated_client, party=str(customer.id))

    assert Debt.objects.filter(source_transaction_id=response.data["id"]).exists() is False


def test_credit_sale_without_a_party_creates_no_debt(authenticated_client, business):
    response = record(authenticated_client, payment_status=PaymentStatus.CREDIT)

    assert response.status_code == status.HTTP_201_CREATED
    assert Debt.objects.count() == 0


def test_paying_the_debt_settles_the_transaction(authenticated_client, customer):
    response = record(
        authenticated_client,
        amount="800.00",
        payment_status=PaymentStatus.CREDIT,
        party=str(customer.id),
    )
    debt = Debt.objects.get(source_transaction_id=response.data["id"])

    authenticated_client.post(
        reverse("debt-payments", args=[debt.id]), {"amount": "800.00"}, format="json"
    )

    txn = Transaction.objects.get(id=response.data["id"])
    assert txn.payment_status == PaymentStatus.PAID
    assert txn.amount_paid == Decimal("800.00")
    assert txn.outstanding_amount == Decimal("0.00")


def test_part_payment_of_the_debt_shows_on_the_transaction(
    authenticated_client, customer
):
    response = record(
        authenticated_client,
        amount="800.00",
        payment_status=PaymentStatus.CREDIT,
        party=str(customer.id),
    )
    debt = Debt.objects.get(source_transaction_id=response.data["id"])

    authenticated_client.post(
        reverse("debt-payments", args=[debt.id]), {"amount": "300.00"}, format="json"
    )

    txn = Transaction.objects.get(id=response.data["id"])
    assert txn.payment_status == PaymentStatus.PARTIAL
    assert txn.outstanding_amount == Decimal("500.00")


def test_transaction_settlement_cannot_bypass_the_debt(authenticated_client, customer):
    response = record(
        authenticated_client,
        amount="800.00",
        payment_status=PaymentStatus.CREDIT,
        party=str(customer.id),
    )
    txn = Transaction.objects.get(id=response.data["id"])

    patched = authenticated_client.patch(
        transaction_url(txn), {"amount_paid": "800.00"}, format="json"
    )

    assert patched.status_code == status.HTTP_400_BAD_REQUEST
    txn.refresh_from_db()
    assert txn.amount_paid == Decimal("0.00")


def test_correcting_the_transaction_amount_moves_the_debt(
    authenticated_client, customer
):
    response = record(
        authenticated_client,
        amount="800.00",
        payment_status=PaymentStatus.CREDIT,
        party=str(customer.id),
    )
    txn = Transaction.objects.get(id=response.data["id"])

    patched = authenticated_client.patch(
        transaction_url(txn), {"amount": "1000.00"}, format="json"
    )

    assert patched.status_code == status.HTTP_200_OK
    debt = Debt.objects.get(source_transaction=txn)
    assert debt.original_amount == Decimal("1000.00")
    assert debt.balance == Decimal("1000.00")


def test_correction_cannot_go_below_what_was_already_paid(
    authenticated_client, customer
):
    response = record(
        authenticated_client,
        amount="800.00",
        payment_status=PaymentStatus.CREDIT,
        party=str(customer.id),
    )
    txn = Transaction.objects.get(id=response.data["id"])
    debt = Debt.objects.get(source_transaction=txn)
    authenticated_client.post(
        reverse("debt-payments", args=[debt.id]), {"amount": "500.00"}, format="json"
    )

    patched = authenticated_client.patch(
        transaction_url(txn), {"amount": "300.00"}, format="json"
    )

    assert patched.status_code == status.HTTP_400_BAD_REQUEST


def test_debt_from_a_transaction_cannot_be_edited_directly(
    authenticated_client, customer
):
    response = record(
        authenticated_client,
        amount="800.00",
        payment_status=PaymentStatus.CREDIT,
        party=str(customer.id),
    )
    debt = Debt.objects.get(source_transaction_id=response.data["id"])

    patched = authenticated_client.patch(
        reverse("debt-detail", args=[debt.id]),
        {"original_amount": "900.00"},
        format="json",
    )

    assert patched.status_code == status.HTTP_400_BAD_REQUEST
