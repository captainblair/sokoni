"""Transactions may reference a party and a product, but only from their own business."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.catalog.models import Product
from apps.ledger.models import Transaction, TransactionType
from apps.parties.models import Party, PartyType

pytestmark = pytest.mark.django_db

LIST_URL = reverse("transaction-list")


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def supplier(business):
    return Party.objects.create(
        business=business, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )


@pytest.fixture
def product(business):
    return Product.objects.create(business=business, name="Soda crate", unit="crate")


@pytest.fixture
def rival_party(other_business):
    return Party.objects.create(business=other_business, name="Rival Customer")


@pytest.fixture
def rival_product(other_business):
    return Product.objects.create(business=other_business, name="Rival Stock")


def test_sale_can_reference_a_customer_and_product(
    authenticated_client, business, customer, product
):
    response = authenticated_client.post(
        LIST_URL,
        {
            "transaction_type": TransactionType.SALE,
            "amount": "2400.00",
            "party": str(customer.id),
            "product": str(product.id),
            "quantity": "2",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["party_name"] == "Mary Wanjiku"
    assert response.data["product_name"] == "Soda crate"


def test_purchase_can_reference_a_supplier(authenticated_client, business, supplier):
    response = authenticated_client.post(
        LIST_URL,
        {
            "transaction_type": TransactionType.PURCHASE,
            "amount": "800.00",
            "party": str(supplier.id),
            "payment_status": "credit",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Decimal(response.data["outstanding_amount"]) == Decimal("800.00")


def test_cannot_attach_a_party_from_another_business(
    authenticated_client, business, rival_party
):
    response = authenticated_client.post(
        LIST_URL,
        {
            "transaction_type": TransactionType.SALE,
            "amount": "100.00",
            "party": str(rival_party.id),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "party" in response.data
    assert Transaction.objects.count() == 0


def test_cannot_attach_a_product_from_another_business(
    authenticated_client, business, rival_product
):
    response = authenticated_client.post(
        LIST_URL,
        {
            "transaction_type": TransactionType.SALE,
            "amount": "100.00",
            "product": str(rival_product.id),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "product" in response.data


def test_archiving_a_party_keeps_its_transactions(
    authenticated_client, business, customer
):
    authenticated_client.post(
        LIST_URL,
        {
            "transaction_type": TransactionType.SALE,
            "amount": "500.00",
            "party": str(customer.id),
        },
        format="json",
    )

    customer.archive()

    # History must survive the customer being archived.
    assert Transaction.objects.filter(party=customer).count() == 1


def test_deleting_a_party_keeps_its_transactions(authenticated_client, business, customer):
    created = authenticated_client.post(
        LIST_URL,
        {
            "transaction_type": TransactionType.SALE,
            "amount": "500.00",
            "party": str(customer.id),
        },
        format="json",
    )
    txn = Transaction.objects.get(id=created.data["id"])

    customer.delete()

    txn.refresh_from_db()
    assert txn.party is None
    assert txn.amount == Decimal("500.00")
