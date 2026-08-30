"""Financial records must never cross a business boundary."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.ledger.models import Transaction, TransactionType

pytestmark = pytest.mark.django_db

LIST_URL = reverse("transaction-list")


def detail_url(txn):
    return reverse("transaction-detail", args=[txn.id])


@pytest.fixture
def rival_transaction(other_business):
    return Transaction.objects.create(
        business=other_business,
        transaction_type=TransactionType.SALE,
        amount=Decimal("9000.00"),
        amount_paid=Decimal("9000.00"),
        description="Rival takings",
    )


def test_another_businesss_transactions_are_invisible(
    authenticated_client, business, rival_transaction
):
    response = authenticated_client.get(LIST_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


def test_cannot_retrieve_another_businesss_transaction(
    authenticated_client, business, rival_transaction
):
    response = authenticated_client.get(detail_url(rival_transaction))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_cannot_edit_another_businesss_transaction(
    authenticated_client, business, rival_transaction
):
    response = authenticated_client.patch(
        detail_url(rival_transaction), {"amount": "1.00"}, format="json"
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    rival_transaction.refresh_from_db()
    assert rival_transaction.amount == Decimal("9000.00")


def test_cannot_archive_another_businesss_transaction(
    authenticated_client, business, rival_transaction
):
    response = authenticated_client.delete(detail_url(rival_transaction))

    assert response.status_code == status.HTTP_404_NOT_FOUND
    rival_transaction.refresh_from_db()
    assert rival_transaction.is_active is True


def test_cannot_record_a_transaction_in_another_business(
    authenticated_client, other_business
):
    response = authenticated_client.post(
        LIST_URL,
        {
            "transaction_type": TransactionType.SALE,
            "amount": "100.00",
            "business": str(other_business.id),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Transaction.objects.filter(business=other_business).count() == 0


def test_ledger_requires_authentication(api_client, business):
    assert api_client.get(LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED


def test_a_member_can_record_transactions(client_for, business, other_user):
    from apps.businesses.models import Membership, MembershipRole

    Membership.objects.create(business=business, user=other_user, role=MembershipRole.MEMBER)
    other_user.active_business = business
    other_user.save(update_fields=["active_business"])

    response = client_for(other_user).post(
        LIST_URL,
        {"transaction_type": TransactionType.SALE, "amount": "300.00"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
