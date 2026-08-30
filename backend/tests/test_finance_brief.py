"""The daily brief: numbers said back in sentences, with claims labelled."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.debts.models import DebtType
from apps.debts.services import create_debt
from apps.finance.brief import format_money
from apps.ledger.models import TransactionType
from apps.ledger.services import record_transaction
from apps.parties.models import Party, PartyType

pytestmark = pytest.mark.django_db

URL = reverse("daily-brief")


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def supplier(business):
    return Party.objects.create(
        business=business, name="Jane Tomatoes", party_type=PartyType.SUPPLIER
    )


def brief(client):
    response = client.get(URL)
    assert response.status_code == status.HTTP_200_OK
    return response.data


def lines(data):
    return [message["text"] for message in data["messages"]]


def test_money_is_formatted_the_way_it_is_spoken():
    assert format_money(Decimal("8500.00"), "KES") == "KES 8,500"
    assert format_money(Decimal("8500.50"), "KES") == "KES 8,500.50"
    assert format_money(Decimal("0.00"), "KES") == "KES 0"


def test_a_quiet_day_still_gives_a_brief(authenticated_client, business):
    data = brief(authenticated_client)

    assert data["headline"] == "You have KES 0 available."
    assert "Nothing has been recorded today yet." in lines(data)


def test_the_brief_leads_with_available_cash(authenticated_client, business, user):
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("2400.00"),
    )

    data = brief(authenticated_client)

    assert data["headline"] == "You have KES 2,400 available."
    assert Decimal(data["cash_position"]["available_cash"]) == Decimal("2400.00")


def test_the_brief_reports_todays_trading(authenticated_client, business, user):
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("2400.00"),
    )
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.EXPENSE,
        amount=Decimal("500.00"),
    )

    assert (
        "Today you took in KES 2,400 and spent KES 500 across 2 entries."
        in lines(brief(authenticated_client))
    )


def test_the_brief_names_what_is_owed(
    authenticated_client, business, user, customer, supplier
):
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
    )

    spoken = lines(brief(authenticated_client))

    assert "Customers owe you KES 4,200." in spoken
    assert "You owe KES 6,000." in spoken


def test_late_debts_are_called_out(authenticated_client, business, user, customer):
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.RECEIVABLE,
        party=customer,
        original_amount=Decimal("1200.00"),
        due_date=timezone.localdate() - timedelta(days=4),
    )

    spoken = " ".join(lines(brief(authenticated_client)))

    assert "KES 1,200 of that is already late." in spoken


def test_a_shortfall_is_labelled_an_estimate(
    authenticated_client, business, user, supplier
):
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("1000.00"),
    )
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.PAYABLE,
        party=supplier,
        original_amount=Decimal("6000.00"),
        due_date=timezone.localdate() + timedelta(days=2),
    )

    data = brief(authenticated_client)
    shortfall = [m for m in data["messages"] if "short" in m["text"]]

    assert len(shortfall) == 1
    assert shortfall[0]["kind"] == "estimate"
    assert "KES 5,000" in shortfall[0]["text"]


def test_covered_obligations_are_stated_as_fact(
    authenticated_client, business, user, supplier
):
    record_transaction(
        business=business,
        created_by=user,
        transaction_type=TransactionType.SALE,
        amount=Decimal("9000.00"),
    )
    create_debt(
        business=business,
        created_by=user,
        debt_type=DebtType.PAYABLE,
        party=supplier,
        original_amount=Decimal("2000.00"),
        due_date=timezone.localdate() + timedelta(days=2),
    )

    data = brief(authenticated_client)
    due = [m for m in data["messages"] if "due in the next" in m["text"]]

    assert due[0]["kind"] == "fact"
    assert all(m["kind"] in {"fact", "estimate"} for m in data["messages"])


def test_the_brief_carries_the_numbers_behind_the_words(
    authenticated_client, business, user
):
    data = brief(authenticated_client)

    assert set(data) >= {
        "headline",
        "messages",
        "cash_position",
        "today",
        "float_risk",
        "generated_at",
    }
    assert data["today"]["period"] == "today"
