"""Answering "who owes me?" and "how late are they?"."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.debts.models import AgingBucket, Debt, DebtStatus, DebtType
from apps.parties.models import Party

pytestmark = pytest.mark.django_db

LIST_URL = reverse("debt-list")


def ids(response):
    return {item["id"] for item in response.data}


@pytest.fixture
def book(business):
    today = timezone.localdate()
    mary = Party.objects.create(business=business, name="Mary Wanjiku")
    jane = Party.objects.create(business=business, name="Jane Tomatoes")

    return {
        "mary": Debt.objects.create(
            business=business,
            debt_type=DebtType.RECEIVABLE,
            party=mary,
            original_amount=Decimal("800.00"),
            due_date=today - timedelta(days=3),
        ),
        "jane": Debt.objects.create(
            business=business,
            debt_type=DebtType.PAYABLE,
            party=jane,
            original_amount=Decimal("1200.00"),
            due_date=today + timedelta(days=5),
        ),
        "old": Debt.objects.create(
            business=business,
            debt_type=DebtType.RECEIVABLE,
            party=mary,
            original_amount=Decimal("400.00"),
            amount_paid=Decimal("400.00"),
            status=DebtStatus.SETTLED,
            due_date=today - timedelta(days=90),
        ),
    }


def test_filter_by_type(authenticated_client, book):
    response = authenticated_client.get(LIST_URL, {"type": DebtType.PAYABLE})

    assert ids(response) == {str(book["jane"].id)}


def test_filter_by_status(authenticated_client, book):
    response = authenticated_client.get(LIST_URL, {"status": DebtStatus.SETTLED})

    assert ids(response) == {str(book["old"].id)}


def test_filter_outstanding_only(authenticated_client, book):
    response = authenticated_client.get(LIST_URL, {"outstanding": "true"})

    assert ids(response) == {str(book["mary"].id), str(book["jane"].id)}


def test_filter_overdue_only(authenticated_client, book):
    response = authenticated_client.get(LIST_URL, {"overdue": "true"})

    assert ids(response) == {str(book["mary"].id)}


def test_filter_by_party(authenticated_client, book):
    response = authenticated_client.get(LIST_URL, {"party": str(book["mary"].party_id)})

    assert ids(response) == {str(book["mary"].id), str(book["old"].id)}


def test_search_matches_the_party_name(authenticated_client, book):
    response = authenticated_client.get(LIST_URL, {"search": "jane"})

    assert ids(response) == {str(book["jane"].id)}


def test_overdue_debt_reports_days_and_bucket(authenticated_client, book):
    response = authenticated_client.get(
        reverse("debt-detail", args=[book["mary"].id])
    )

    assert response.data["is_overdue"] is True
    assert response.data["days_overdue"] == 3
    assert response.data["aging_bucket"] == AgingBucket.DUE_1_7


def test_aging_buckets_widen_with_time(business):
    party = Party.objects.create(business=business, name="Late Payer")
    today = timezone.localdate()

    def debt_due(days_ago):
        return Debt(
            business=business,
            debt_type=DebtType.RECEIVABLE,
            party=party,
            original_amount=Decimal("100.00"),
            due_date=today - timedelta(days=days_ago),
        )

    assert debt_due(0).aging_bucket == AgingBucket.CURRENT
    assert debt_due(20).aging_bucket == AgingBucket.DUE_8_30
    assert debt_due(45).aging_bucket == AgingBucket.DUE_31_60
    assert debt_due(120).aging_bucket == AgingBucket.DUE_60_PLUS


def test_settled_debt_is_never_overdue(book):
    assert book["old"].is_overdue is False
    assert book["old"].days_overdue == 0


def test_list_is_ordered_by_due_date(authenticated_client, book):
    response = authenticated_client.get(LIST_URL, {"outstanding": "true"})

    assert [item["id"] for item in response.data] == [
        str(book["mary"].id),
        str(book["jane"].id),
    ]
