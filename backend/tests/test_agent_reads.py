"""Asking the agent questions, and being answered in sentences."""

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

URL = reverse("agent-execute")


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def supplier(business):
    return Party.objects.create(
        business=business, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )


@pytest.fixture
def books(business, user, customer, supplier):
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("9000.00"),
    )
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("500.00"),
    )
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("4200.00"),
    )
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.PAYABLE,
        party=supplier,
        original_amount=Decimal("6000.00"),
        due_date=timezone.localdate() + timedelta(days=2),
    )


def ask(client, tool, parameters=None):
    response = client.post(
        URL, {"tool": tool, "parameters": parameters or {}}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK, response.data
    return response.data


def test_a_question_never_creates_anything(authenticated_client, books):
    from apps.ledger.models import Transaction

    before = Transaction.objects.count()
    ask(authenticated_client, "get_cash_position")

    assert Transaction.objects.count() == before


def test_cash_position_answers_in_words(authenticated_client, books):
    answer = ask(authenticated_client, "get_cash_position")

    assert answer["message"] == "You have KES 8,500 available."
    assert Decimal(answer["data"]["receivables"]) == Decimal("4200.00")


def test_a_summary_reports_the_estimate_as_an_estimate(authenticated_client, books):
    answer = ask(authenticated_client, "get_summary", {"period": "today"})

    assert answer["message"] == (
        "Today you took in KES 9,000 and spent KES 500, leaving an estimated "
        "KES 8,500."
    )


def test_an_unknown_period_is_refused(authenticated_client, books):
    response = authenticated_client.post(
        URL,
        {"tool": "get_summary", "parameters": {"period": "fortnight"}},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["status"] == "rejected"


def test_float_risk_is_answered_plainly(authenticated_client, books):
    answer = ask(authenticated_client, "check_float_risk")

    assert "due in the next 7 days" in answer["message"]
    assert answer["data"]["risk_level"] == "none"


def test_the_debts_are_listed_and_totalled(authenticated_client, books):
    answer = ask(authenticated_client, "get_debts")

    assert "2 outstanding, KES 10,200 in total" in answer["message"]
    assert len(answer["data"]) == 2


def test_debts_can_be_asked_for_in_one_direction(authenticated_client, books):
    answer = ask(authenticated_client, "get_debts", {"direction": "payable"})

    assert len(answer["data"]) == 1
    assert "Jane Tomatoes KES 6,000" in answer["message"]


def test_no_debts_is_a_clear_answer(authenticated_client, business):
    answer = ask(authenticated_client, "get_debts")

    assert answer["message"] == "There are no outstanding debts."
    assert answer["data"] == []


def test_one_persons_balance(authenticated_client, books):
    answer = ask(authenticated_client, "get_party_balance", {"party": "Mary"})

    assert answer["message"] == "Mary Wanjiku owes you KES 4,200."
    assert Decimal(answer["data"]["net_balance"]) == Decimal("4200.00")


def test_a_supplier_balance_reads_the_other_way(authenticated_client, books):
    answer = ask(authenticated_client, "get_party_balance", {"party": "Jane"})

    assert answer["message"] == "You owe Jane Tomatoes KES 6,000."


def test_a_settled_party_is_said_to_be_settled(authenticated_client, business, customer):
    answer = ask(authenticated_client, "get_party_balance", {"party": "Mary"})

    assert answer["message"] == "You and Mary Wanjiku are settled up."


def test_asking_about_a_stranger_creates_nobody(authenticated_client, business):
    response = authenticated_client.post(
        URL,
        {"tool": "get_party_balance", "parameters": {"party": "Nobody"}},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Party.objects.filter(business=business).count() == 0


def test_recent_transactions_are_read_back(authenticated_client, books):
    answer = ask(authenticated_client, "get_recent_transactions", {"limit": 2})

    assert len(answer["data"]) == 2
    assert "The last 2:" in answer["message"]


def test_the_daily_brief_comes_through_the_agent(authenticated_client, books):
    answer = ask(authenticated_client, "get_daily_brief")

    assert "You have KES 8,500 available." in answer["message"]
    assert answer["data"]["headline"] == "You have KES 8,500 available."
    assert all(m["kind"] in {"fact", "estimate"} for m in answer["data"]["messages"])
