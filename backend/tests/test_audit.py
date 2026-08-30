"""Money mutations leave a trail that cannot be rewritten."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.audit.models import AuditAction, AuditEvent, AuditIntegrityError, AuditObjectType
from apps.debts.models import DebtType
from apps.debts.services import create_debt, record_payment, write_off_debt
from apps.ledger.models import PaymentStatus, TransactionType
from apps.ledger.services import record_transaction, update_transaction
from apps.parties.models import Party

pytestmark = pytest.mark.django_db

LIST_URL = reverse("audit-event-list")


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


def test_recording_a_sale_writes_an_audit_event(business, user):
    txn = record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("2400.00"),
    )

    event = AuditEvent.objects.get(object_id=txn.id)
    assert event.action == AuditAction.CREATED
    assert event.object_type == AuditObjectType.TRANSACTION
    assert event.actor == user
    assert event.business == business
    assert event.after["amount"] == "2400.00"
    assert "2400" in event.summary


def test_a_credit_sale_audits_both_the_transaction_and_the_debt(
    business, user, customer
):
    txn = record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("800.00"),
        payment_status=PaymentStatus.CREDIT,
        party=customer,
    )

    kinds = set(AuditEvent.objects.values_list("object_type", flat=True))
    assert kinds == {AuditObjectType.TRANSACTION, AuditObjectType.DEBT}
    assert AuditEvent.objects.get(object_id=txn.debt.id).action == AuditAction.CREATED


def test_correcting_a_transaction_keeps_the_before_picture(business, user):
    txn = record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("24000.00"),
    )

    update_transaction(txn, amount=Decimal("2400.00"))

    correction = AuditEvent.objects.filter(
        object_id=txn.id, action=AuditAction.UPDATED
    ).get()
    assert correction.before["amount"] == "24000.00"
    assert correction.after["amount"] == "2400.00"


def test_a_debt_payment_is_audited(business, user, customer):
    debt = create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("800.00"),
    )
    record_payment(debt, amount=Decimal("300.00"), created_by=user)

    event = AuditEvent.objects.get(object_type=AuditObjectType.DEBT_PAYMENT)
    assert event.action == AuditAction.PAID
    assert event.after["amount"] == "300.00"
    assert event.before["amount_paid"] == "0.00"


def test_a_write_off_is_audited(business, user, customer):
    debt = create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("400.00"),
    )
    write_off_debt(debt, notes="Moved away", actor=user)

    event = AuditEvent.objects.get(action=AuditAction.WRITTEN_OFF)
    assert event.actor == user
    assert "400" in event.summary


def test_archiving_a_transaction_is_audited(authenticated_client, business, user):
    txn = record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("500.00"),
    )

    response = authenticated_client.delete(
        reverse("transaction-detail", args=[txn.id])
    )

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert AuditEvent.objects.filter(
        object_id=txn.id, action=AuditAction.ARCHIVED
    ).exists()


def test_the_trail_is_listed_for_the_business(authenticated_client, business, user):
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("100.00"),
    )

    response = authenticated_client.get(LIST_URL)

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    assert response.data[0]["actor_email"] == user.email


def test_another_businesss_trail_is_invisible(
    authenticated_client, business, other_business, other_user
):
    record_transaction(
        business=other_business,
        created_by=other_user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("9999.00"),
    )

    response = authenticated_client.get(LIST_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.data == []


def test_a_foreign_event_is_not_found(
    authenticated_client, business, other_business, other_user
):
    txn = record_transaction(
        business=other_business,
        created_by=other_user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("100.00"),
    )
    event = AuditEvent.objects.get(object_id=txn.id)

    response = authenticated_client.get(reverse("audit-event-detail", args=[event.id]))

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_the_trail_cannot_be_posted_to(authenticated_client, business):
    response = authenticated_client.post(
        LIST_URL, {"action": "created", "summary": "nope"}, format="json"
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_an_event_cannot_be_changed(business, user):
    txn = record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("100.00"),
    )
    event = AuditEvent.objects.get(object_id=txn.id)

    event.summary = "rewritten"
    with pytest.raises(AuditIntegrityError):
        event.save()


def test_an_event_cannot_be_deleted(business, user):
    txn = record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("100.00"),
    )
    event = AuditEvent.objects.get(object_id=txn.id)

    with pytest.raises(AuditIntegrityError):
        event.delete()

    assert AuditEvent.objects.filter(pk=event.pk).exists()


def test_the_trail_requires_authentication(api_client):
    assert api_client.get(LIST_URL).status_code == status.HTTP_401_UNAUTHORIZED
