from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.ledger.models import PaymentStatus, Transaction, TransactionSource, TransactionType

pytestmark = pytest.mark.django_db

LIST_URL = reverse("transaction-list")


def detail_url(txn):
    return reverse("transaction-detail", args=[txn.id])


def record(client, **overrides):
    payload = {"transaction_type": TransactionType.SALE, "amount": "2400.00"}
    payload.update(overrides)
    return client.post(LIST_URL, payload, format="json")


def test_record_a_paid_sale(authenticated_client, business, user):
    response = record(authenticated_client, description="Two crates of soda")

    assert response.status_code == status.HTTP_201_CREATED
    assert Decimal(response.data["amount"]) == Decimal("2400.00")
    assert response.data["payment_status"] == PaymentStatus.PAID
    assert Decimal(response.data["amount_paid"]) == Decimal("2400.00")
    assert Decimal(response.data["outstanding_amount"]) == Decimal("0.00")
    assert response.data["currency"] == "KES"
    assert response.data["source"] == TransactionSource.MANUAL

    txn = Transaction.objects.get(id=response.data["id"])
    assert txn.business == business
    assert txn.created_by == user


def test_record_an_expense(authenticated_client, business):
    response = record(
        authenticated_client,
        transaction_type=TransactionType.EXPENSE,
        amount="500.00",
        description="Fare",
    )

    assert response.status_code == status.HTTP_201_CREATED
    txn = Transaction.objects.get(id=response.data["id"])
    assert txn.is_money_in is False
    assert txn.signed_amount == Decimal("-500.00")


def test_money_in_and_out_are_signed_correctly(authenticated_client, business):
    sale = record(authenticated_client, amount="1000.00")
    purchase = record(
        authenticated_client, transaction_type=TransactionType.PURCHASE, amount="400.00"
    )

    assert Decimal(sale.data["signed_amount"]) == Decimal("1000.00")
    assert Decimal(purchase.data["signed_amount"]) == Decimal("-400.00")


def test_credit_sale_leaves_the_full_amount_outstanding(authenticated_client, business):
    response = record(authenticated_client, payment_status=PaymentStatus.CREDIT)

    assert response.status_code == status.HTTP_201_CREATED
    assert Decimal(response.data["amount_paid"]) == Decimal("0.00")
    assert Decimal(response.data["outstanding_amount"]) == Decimal("2400.00")


def test_partial_payment_derives_the_status(authenticated_client, business):
    response = record(authenticated_client, amount="2000.00", amount_paid="500.00")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["payment_status"] == PaymentStatus.PARTIAL
    assert Decimal(response.data["outstanding_amount"]) == Decimal("1500.00")


def test_amount_paid_matching_the_amount_is_treated_as_paid(authenticated_client, business):
    response = record(authenticated_client, amount="2000.00", amount_paid="2000.00")

    assert response.data["payment_status"] == PaymentStatus.PAID


def test_contradictory_payment_information_is_rejected(authenticated_client, business):
    response = record(
        authenticated_client,
        amount="2000.00",
        amount_paid="500.00",
        payment_status=PaymentStatus.PAID,
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_partial_status_without_an_amount_paid_is_rejected(authenticated_client, business):
    response = record(authenticated_client, payment_status=PaymentStatus.PARTIAL)

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_overpayment_is_rejected(authenticated_client, business):
    response = record(authenticated_client, amount="1000.00", amount_paid="1500.00")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_negative_amount_paid_is_rejected(authenticated_client, business):
    response = record(authenticated_client, amount_paid="-100.00")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_zero_amount_is_rejected(authenticated_client, business):
    response = record(authenticated_client, amount="0.00")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_negative_amount_is_rejected(authenticated_client, business):
    response = record(authenticated_client, amount="-2400.00")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_amount_is_calculated_from_quantity_and_unit_price(authenticated_client, business):
    response = record(
        authenticated_client, amount=None, quantity="2", unit_price="1200.00"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Decimal(response.data["amount"]) == Decimal("2400.00")


def test_amount_or_quantity_and_price_are_required(authenticated_client, business):
    response = authenticated_client.post(
        LIST_URL, {"transaction_type": TransactionType.SALE}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "amount" in response.data


def test_future_dated_transactions_are_rejected(authenticated_client, business):
    future = timezone.now() + timezone.timedelta(days=1)

    response = record(authenticated_client, occurred_at=future.isoformat())

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "occurred_at" in response.data


def test_transaction_type_is_required(authenticated_client, business):
    response = authenticated_client.post(LIST_URL, {"amount": "100.00"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "transaction_type" in response.data


def test_currency_follows_the_business(authenticated_client, business):
    business.currency = "UGX"
    business.save(update_fields=["currency"])

    response = record(authenticated_client)

    assert response.data["currency"] == "UGX"


def test_source_can_be_recorded_as_voice(authenticated_client, business):
    response = record(authenticated_client, source=TransactionSource.VOICE)

    assert response.data["source"] == TransactionSource.VOICE
