"""Recording money through the agent layer."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.debts.models import Debt, DebtStatus, DebtType
from apps.debts.services import create_debt
from apps.ledger.models import (
    PaymentStatus,
    Transaction,
    TransactionSource,
    TransactionType,
)
from apps.parties.models import Party, PartyType

pytestmark = pytest.mark.django_db

URL = reverse("agent-execute")


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def supplier(business):
    return Party.objects.create(
        business=business, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )


def call(client, tool, parameters=None, **extra):
    payload = {"tool": tool, "parameters": parameters or {}}
    payload.update(extra)
    return client.post(URL, payload, format="json")


def test_record_a_cash_sale(authenticated_client, business, user):
    response = call(authenticated_client, "record_sale", {"amount": "2400.00"})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "executed"
    assert response.data["message"] == "Recorded a sale of KES 2,400."

    transaction = Transaction.objects.get(business=business)
    assert transaction.transaction_type == TransactionType.SALE
    assert transaction.amount == Decimal("2400.00")
    assert transaction.payment_status == PaymentStatus.PAID
    assert transaction.created_by == user


def test_a_spoken_sale_is_marked_as_coming_from_voice(authenticated_client, business):
    call(authenticated_client, "record_sale", {"amount": "2400.00"})

    assert Transaction.objects.get(business=business).source == TransactionSource.VOICE


def test_quantity_and_price_are_enough(authenticated_client, business):
    response = call(
        authenticated_client,
        "record_sale",
        {"quantity": "2", "unit_price": "1200.00", "product": "Soda crate"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Transaction.objects.get(business=business).amount == Decimal("2400.00")


def test_an_amount_is_required_somehow(authenticated_client, business):
    response = call(authenticated_client, "record_sale", {"description": "something"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_a_sale_on_credit_names_what_is_owed(
    authenticated_client, business, customer
):
    response = call(
        authenticated_client,
        "record_sale",
        {"amount": "800.00", "party": "Mary Wanjiku", "payment_status": "credit"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["message"] == (
        "Recorded a sale of KES 800 to Mary Wanjiku, with KES 800 still owed."
    )
    assert Debt.objects.filter(business=business, party=customer).exists()


def test_an_existing_customer_is_matched_not_duplicated(
    authenticated_client, business, customer
):
    call(authenticated_client, "record_sale", {"amount": "500.00", "party": "mary"})

    assert Party.objects.filter(business=business).count() == 1
    assert Transaction.objects.get(business=business).party == customer


def test_an_expense_is_recorded_as_money_out(authenticated_client, business):
    response = call(
        authenticated_client,
        "record_expense",
        {"amount": "500.00", "description": "Fare to market"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    transaction = Transaction.objects.get(business=business)
    assert transaction.transaction_type == TransactionType.EXPENSE
    assert transaction.is_money_in is False


def test_a_purchase_from_a_supplier(authenticated_client, business, supplier):
    response = call(
        authenticated_client,
        "record_purchase",
        {"amount": "800.00", "party": "Jane Tomatoes", "payment_status": "credit"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    debt = Debt.objects.get(business=business)
    assert debt.debt_type == DebtType.PAYABLE
    assert debt.party == supplier


def test_income_that_is_not_a_sale(authenticated_client, business):
    response = call(authenticated_client, "record_income", {"amount": "300.00"})

    assert response.status_code == status.HTTP_201_CREATED
    assert Transaction.objects.get(business=business).transaction_type == (
        TransactionType.INCOME
    )


def test_create_a_receivable(authenticated_client, business, customer):
    response = call(
        authenticated_client,
        "create_receivable",
        {"party": "Mary Wanjiku", "amount": "800.00", "due_date": "2026-09-30"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["message"] == (
        "Recorded that Mary Wanjiku owes you KES 800, due 2026-09-30."
    )
    debt = Debt.objects.get(business=business)
    assert debt.debt_type == DebtType.RECEIVABLE
    assert debt.source == TransactionSource.VOICE


def test_create_a_payable(authenticated_client, business, supplier):
    response = call(
        authenticated_client,
        "create_payable",
        {"party": "Jane Tomatoes", "amount": "6000.00"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["message"] == "Recorded that you owe Jane Tomatoes KES 6,000."
    assert Debt.objects.get(business=business).debt_type == DebtType.PAYABLE


def test_record_a_payment_against_a_debt(
    authenticated_client, business, user, customer
):
    debt = create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("800.00"),
    )

    response = call(
        authenticated_client,
        "record_debt_payment",
        {"party": "Mary", "amount": "300.00"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["message"] == (
        "Recorded KES 300 received from Mary Wanjiku, leaving KES 500 owed."
    )
    debt.refresh_from_db()
    assert debt.status == DebtStatus.PARTIAL


def test_settling_a_debt_says_so(authenticated_client, business, user, supplier):
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.PAYABLE,
        party=supplier,
        original_amount=Decimal("800.00"),
    )

    response = call(
        authenticated_client,
        "record_debt_payment",
        {"party": "Jane", "amount": "800.00"},
    )

    assert response.data["message"] == (
        "Recorded KES 800 paid to Jane Tomatoes, clearing the debt."
    )


def test_paying_more_than_is_owed_is_refused(
    authenticated_client, business, user, customer
):
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("800.00"),
    )

    response = call(
        authenticated_client,
        "record_debt_payment",
        {"party": "Mary", "amount": "900.00"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["status"] == "rejected"


def test_paying_someone_who_owes_nothing_is_refused(
    authenticated_client, business, customer
):
    response = call(
        authenticated_client,
        "record_debt_payment",
        {"party": "Mary", "amount": "100.00"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "no outstanding debt" in response.data["message"]


def test_paying_a_stranger_writes_nothing(authenticated_client, business):
    response = call(
        authenticated_client,
        "record_debt_payment",
        {"party": "Nobody", "amount": "100.00"},
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Party.objects.filter(business=business).count() == 0


def test_an_unknown_tool_is_rejected(authenticated_client, business):
    response = call(authenticated_client, "delete_everything", {})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "tool" in response.data


def test_a_negative_amount_is_rejected(authenticated_client, business):
    response = call(authenticated_client, "record_sale", {"amount": "-100.00"})

    assert response.status_code == status.HTTP_400_BAD_REQUEST
