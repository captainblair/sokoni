"""Listing, filtering and correcting ledger entries."""

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.ledger.models import (
    PaymentMethod,
    PaymentStatus,
    Transaction,
    TransactionSource,
    TransactionType,
)

pytestmark = pytest.mark.django_db

LIST_URL = reverse("transaction-list")


def detail_url(txn):
    return reverse("transaction-detail", args=[txn.id])


@pytest.fixture
def ledger(business):
    now = timezone.now()
    return {
        "sale": Transaction.objects.create(
            business=business,
            transaction_type=TransactionType.SALE,
            amount=Decimal("2400.00"),
            amount_paid=Decimal("2400.00"),
            payment_method=PaymentMethod.MPESA,
            description="Two crates of soda",
            occurred_at=now,
        ),
        "credit_sale": Transaction.objects.create(
            business=business,
            transaction_type=TransactionType.SALE,
            amount=Decimal("1500.00"),
            amount_paid=Decimal("0.00"),
            payment_status=PaymentStatus.CREDIT,
            occurred_at=now - timezone.timedelta(days=2),
        ),
        "expense": Transaction.objects.create(
            business=business,
            transaction_type=TransactionType.EXPENSE,
            amount=Decimal("500.00"),
            amount_paid=Decimal("500.00"),
            description="Fare to market",
            source=TransactionSource.VOICE,
            occurred_at=now - timezone.timedelta(days=10),
        ),
    }


def ids(response):
    return {item["id"] for item in response.data}


def test_list_returns_the_businesss_ledger(authenticated_client, ledger):
    response = authenticated_client.get(LIST_URL)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 3


def test_list_is_ordered_most_recent_first(authenticated_client, ledger):
    response = authenticated_client.get(LIST_URL)

    assert response.data[0]["id"] == str(ledger["sale"].id)
    assert response.data[-1]["id"] == str(ledger["expense"].id)


def test_filter_by_type(authenticated_client, ledger):
    response = authenticated_client.get(LIST_URL, {"type": TransactionType.EXPENSE})

    assert ids(response) == {str(ledger["expense"].id)}


def test_filter_by_payment_status(authenticated_client, ledger):
    response = authenticated_client.get(LIST_URL, {"status": PaymentStatus.CREDIT})

    assert ids(response) == {str(ledger["credit_sale"].id)}


def test_filter_by_payment_method(authenticated_client, ledger):
    response = authenticated_client.get(LIST_URL, {"method": PaymentMethod.MPESA})

    assert ids(response) == {str(ledger["sale"].id)}


def test_filter_by_source(authenticated_client, ledger):
    response = authenticated_client.get(LIST_URL, {"source": TransactionSource.VOICE})

    assert ids(response) == {str(ledger["expense"].id)}


def test_filter_unsettled_transactions(authenticated_client, ledger):
    response = authenticated_client.get(LIST_URL, {"unsettled": "true"})

    assert ids(response) == {str(ledger["credit_sale"].id)}


def test_filter_by_date_range(authenticated_client, ledger):
    since = (timezone.now() - timezone.timedelta(days=3)).isoformat()

    response = authenticated_client.get(LIST_URL, {"date_from": since})

    assert ids(response) == {str(ledger["sale"].id), str(ledger["credit_sale"].id)}


def test_search_matches_the_description(authenticated_client, ledger):
    response = authenticated_client.get(LIST_URL, {"search": "fare"})

    assert ids(response) == {str(ledger["expense"].id)}


def test_correcting_a_misheard_amount(authenticated_client, ledger):
    txn = ledger["sale"]

    response = authenticated_client.patch(
        detail_url(txn), {"amount": "240.00"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    txn.refresh_from_db()
    assert txn.amount == Decimal("240.00")
    # A fully paid sale stays fully paid at the corrected amount.
    assert txn.amount_paid == Decimal("240.00")
    assert txn.payment_status == PaymentStatus.PAID


def test_recording_a_later_payment_on_a_credit_sale(authenticated_client, ledger):
    txn = ledger["credit_sale"]

    response = authenticated_client.patch(
        detail_url(txn), {"amount_paid": "500.00"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    txn.refresh_from_db()
    assert txn.payment_status == PaymentStatus.PARTIAL
    assert txn.outstanding_amount == Decimal("1000.00")


def test_settling_a_credit_sale_in_full(authenticated_client, ledger):
    txn = ledger["credit_sale"]

    authenticated_client.patch(detail_url(txn), {"amount_paid": "1500.00"}, format="json")

    txn.refresh_from_db()
    assert txn.payment_status == PaymentStatus.PAID
    assert txn.outstanding_amount == Decimal("0.00")


def test_update_cannot_overpay(authenticated_client, ledger):
    response = authenticated_client.patch(
        detail_url(ledger["credit_sale"]), {"amount_paid": "9999.00"}, format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_archiving_a_transaction_hides_it_from_the_ledger(authenticated_client, ledger):
    txn = ledger["expense"]

    response = authenticated_client.delete(detail_url(txn))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    txn.refresh_from_db()
    assert txn.is_active is False
    assert len(authenticated_client.get(LIST_URL).data) == 2
    assert Transaction.objects.filter(id=txn.id).exists()
