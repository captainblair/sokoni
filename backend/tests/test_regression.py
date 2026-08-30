"""
One walk through everything the backend can do, as a trader would.

Later phases will add a voice and a screen. This test is the promise that the
books still add up when those layers arrive, because they will both come
through the same doors.
"""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status

from apps.audit.models import AuditAction, AuditEvent
from tests.conftest import DEFAULT_PASSWORD

pytestmark = pytest.mark.django_db


def test_from_empty_account_to_a_spoken_correction(api_client):
    register = api_client.post(
        reverse("auth-register"),
        {
            "email": "amina@example.com",
            "password": DEFAULT_PASSWORD,
            "password_confirm": DEFAULT_PASSWORD,
            "full_name": "Amina Trader",
        },
        format="json",
    )
    assert register.status_code == status.HTTP_201_CREATED
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {register.data['access']}")

    shop = api_client.post(
        reverse("business-list"),
        {"name": "Amina Groceries", "currency": "KES"},
        format="json",
    )
    assert shop.status_code == status.HTTP_201_CREATED

    mary = api_client.post(
        reverse("party-list"), {"name": "Mary Wanjiku"}, format="json"
    )
    jane = api_client.post(
        reverse("party-list"),
        {"name": "Jane Tomatoes", "party_type": "supplier"},
        format="json",
    )
    soda = api_client.post(
        reverse("product-list"),
        {"name": "Soda crate", "unit": "crate", "default_price": "1200.00"},
        format="json",
    )
    assert {mary.status_code, jane.status_code, soda.status_code} == {
        status.HTTP_201_CREATED
    }

    paid_sale = api_client.post(
        reverse("transaction-list"),
        {
            "transaction_type": "sale",
            "quantity": "2",
            "unit_price": "1200.00",
            "product": soda.data["id"],
            "party": mary.data["id"],
            "payment_method": "mpesa",
        },
        format="json",
    )
    assert paid_sale.status_code == status.HTTP_201_CREATED
    assert Decimal(paid_sale.data["amount"]) == Decimal("2400.00")

    credit = api_client.post(
        reverse("transaction-list"),
        {
            "transaction_type": "purchase",
            "amount": "800.00",
            "party": jane.data["id"],
            "payment_status": "credit",
            "description": "Tomatoes taken on credit",
        },
        format="json",
    )
    assert credit.status_code == status.HTTP_201_CREATED

    debts = api_client.get(reverse("debt-list"), {"outstanding": "true"})
    assert len(debts.data) == 1
    debt_id = debts.data[0]["id"]

    part = api_client.post(
        reverse("debt-payments", args=[debt_id]),
        {"amount": "500.00", "payment_method": "cash"},
        format="json",
    )
    assert part.status_code == status.HTTP_201_CREATED

    cash = api_client.get(reverse("cash-position"))
    assert Decimal(cash.data["available_cash"]) == Decimal("1900.00")
    assert Decimal(cash.data["payables"]) == Decimal("300.00")

    brief = api_client.get(reverse("daily-brief"))
    assert brief.data["headline"] == "You have KES 1,900 available."

    spoken = api_client.post(
        reverse("agent-execute"),
        {
            "tool": "record_sale",
            "parameters": {"amount": "2400.00", "party": "Mary Wanjiku"},
            "confidence": 0.4,
        },
        format="json",
    )
    assert spoken.data["status"] == "confirmation_required"

    confirmed = api_client.post(
        reverse("agent-execute"),
        {
            "tool": "record_sale",
            "confirmation_token": spoken.data["confirmation"]["token"],
        },
        format="json",
    )
    assert confirmed.status_code == status.HTTP_201_CREATED
    assert confirmed.data["message"] == "Recorded a sale of KES 2,400 to Mary Wanjiku."

    cash = api_client.get(reverse("cash-position"))
    assert Decimal(cash.data["available_cash"]) == Decimal("4300.00")

    trail = api_client.get(reverse("audit-event-list"))
    actions = {event["action"] for event in trail.data}
    assert {AuditAction.CREATED, AuditAction.PAID} <= actions
    assert AuditEvent.objects.filter(action=AuditAction.CREATED).count() >= 3

    schema = api_client.get(reverse("schema"), HTTP_ACCEPT="application/json")
    assert schema.status_code == status.HTTP_200_OK
    assert "/api/v1/agent/execute/" in schema.data["paths"]
