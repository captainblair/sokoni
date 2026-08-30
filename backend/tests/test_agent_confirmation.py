"""When Sokoni commits, and when it stops to ask."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.agent.models import ConfirmationReason, PendingAction
from apps.ledger.models import Transaction, TransactionType
from apps.parties.models import Party

pytestmark = pytest.mark.django_db

URL = reverse("agent-execute")


@pytest.fixture
def customer(business):
    return Party.objects.create(business=business, name="Mary Wanjiku")


@pytest.fixture
def trading_history(business):
    """Enough ordinary sales for "unusual" to mean something."""
    for _ in range(6):
        Transaction.objects.create(
            business=business,
            transaction_type=TransactionType.SALE,
            amount=Decimal("2400.00"),
            amount_paid=Decimal("2400.00"),
        )


def call(client, tool, parameters=None, **extra):
    payload = {"tool": tool, "parameters": parameters or {}}
    payload.update(extra)
    return client.post(URL, payload, format="json")


def confirm(client, token, tool):
    return client.post(
        URL, {"tool": tool, "confirmation_token": token}, format="json"
    )


# --------------------------------------------------------------------------- #
# Low confidence
# --------------------------------------------------------------------------- #


def test_low_confidence_asks_before_recording(authenticated_client, business):
    response = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.4
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "confirmation_required"
    assert response.data["message"] == "Did you mean a sale of KES 2,400?"
    assert response.data["confirmation"]["reason"] == ConfirmationReason.LOW_CONFIDENCE
    assert Transaction.objects.count() == 0


def test_high_confidence_records_straight_away(authenticated_client, business):
    response = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.95
    )

    assert response.data["status"] == "executed"
    assert Transaction.objects.count() == 1


def test_confidence_is_optional(authenticated_client, business):
    response = call(authenticated_client, "record_sale", {"amount": "2400.00"})

    assert response.data["status"] == "executed"


def test_confirming_commits_the_write(authenticated_client, business):
    token = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.4
    ).data["confirmation"]["token"]

    response = confirm(authenticated_client, token, "record_sale")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "executed"
    assert Transaction.objects.get().amount == Decimal("2400.00")


def test_a_confirmation_works_only_once(authenticated_client, business):
    token = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.4
    ).data["confirmation"]["token"]
    confirm(authenticated_client, token, "record_sale")

    response = confirm(authenticated_client, token, "record_sale")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 1


def test_an_expired_confirmation_is_refused(authenticated_client, business):
    token = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.4
    ).data["confirmation"]["token"]

    pending = PendingAction.objects.get(token=token)
    pending.expires_at = timezone.now() - timedelta(seconds=1)
    pending.save(update_fields=["expires_at"])

    response = confirm(authenticated_client, token, "record_sale")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0


def test_an_unknown_token_is_refused(authenticated_client, business):
    response = confirm(authenticated_client, "not-a-real-token", "record_sale")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_a_token_cannot_be_used_for_another_tool(authenticated_client, business):
    token = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.4
    ).data["confirmation"]["token"]

    response = confirm(authenticated_client, token, "record_expense")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0


def test_another_user_cannot_redeem_the_token(
    authenticated_client, client_for, business, other_user
):
    from apps.businesses.models import Membership, MembershipRole

    Membership.objects.create(
        business=business, user=other_user, role=MembershipRole.MEMBER
    )
    token = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.4
    ).data["confirmation"]["token"]

    response = client_for(other_user).post(
        URL,
        {
            "tool": "record_sale",
            "confirmation_token": token,
            "business": str(business.id),
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0


def test_a_confirmation_cannot_smuggle_different_figures(
    authenticated_client, business
):
    token = call(
        authenticated_client, "record_sale", {"amount": "2400.00"}, confidence=0.4
    ).data["confirmation"]["token"]

    response = authenticated_client.post(
        URL,
        {
            "tool": "record_sale",
            "confirmation_token": token,
            "parameters": {"amount": "24000.00"},
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert Transaction.objects.count() == 0


# --------------------------------------------------------------------------- #
# Amounts unlike this business
# --------------------------------------------------------------------------- #


def test_a_misheard_decimal_is_questioned(authenticated_client, trading_history):
    response = call(
        authenticated_client, "record_sale", {"amount": "24000.00"}, confidence=1.0
    )

    assert response.data["status"] == "confirmation_required"
    assert response.data["confirmation"]["reason"] == ConfirmationReason.UNUSUAL_AMOUNT
    assert "much larger than usual" in response.data["message"]
    assert Transaction.objects.count() == 6


def test_an_ordinary_amount_passes_without_a_question(
    authenticated_client, trading_history
):
    response = call(
        authenticated_client, "record_sale", {"amount": "2600.00"}, confidence=1.0
    )

    assert response.data["status"] == "executed"


def test_without_history_size_is_not_judged(authenticated_client, business):
    response = call(
        authenticated_client, "record_sale", {"amount": "990000.00"}, confidence=1.0
    )

    # Nothing to compare against yet, so there is no honest basis for doubt.
    assert response.data["status"] == "executed"


def test_reads_are_never_confirmed(authenticated_client, trading_history):
    response = call(authenticated_client, "get_cash_position", {}, confidence=0.1)

    assert response.data["status"] == "executed"


# --------------------------------------------------------------------------- #
# Names nobody has traded with
# --------------------------------------------------------------------------- #


@pytest.mark.django_db(transaction=True)
def test_a_new_name_is_confirmed_before_a_record_appears(
    authenticated_client, business
):
    response = call(
        authenticated_client,
        "record_sale",
        {"amount": "500.00", "party": "Maggie"},
        confidence=1.0,
    )

    assert response.data["status"] == "confirmation_required"
    assert response.data["confirmation"]["reason"] == ConfirmationReason.NEW_PARTY
    assert "Maggie has not traded here before" in response.data["message"]
    # The rolled-back preparation left nothing behind.
    assert Party.objects.filter(business=business).count() == 0
    assert Transaction.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_confirming_a_new_name_creates_it(authenticated_client, business):
    token = call(
        authenticated_client,
        "record_sale",
        {"amount": "500.00", "party": "Maggie"},
        confidence=1.0,
    ).data["confirmation"]["token"]

    response = confirm(authenticated_client, token, "record_sale")

    assert response.status_code == status.HTTP_201_CREATED
    assert Party.objects.get(business=business).name == "Maggie"
    assert Transaction.objects.get().party.name == "Maggie"


def test_a_known_name_needs_no_question(authenticated_client, business, customer):
    response = call(
        authenticated_client,
        "record_sale",
        {"amount": "500.00", "party": "Mary Wanjiku"},
        confidence=1.0,
    )

    assert response.data["status"] == "executed"


# --------------------------------------------------------------------------- #
# Which one did you mean
# --------------------------------------------------------------------------- #


def test_an_ambiguous_name_asks_which(authenticated_client, business):
    Party.objects.create(business=business, name="Mary Wanjiku")
    Party.objects.create(business=business, name="Mary Otieno")

    response = call(
        authenticated_client, "record_sale", {"amount": "500.00", "party": "Mary"}
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "clarification_required"
    assert set(response.data["options"]) == {"Mary Wanjiku", "Mary Otieno"}
    assert response.data["confirmation"] is None
    assert Transaction.objects.count() == 0


def test_a_clarified_name_records_normally(authenticated_client, business):
    Party.objects.create(business=business, name="Mary Wanjiku")
    Party.objects.create(business=business, name="Mary Otieno")

    response = call(
        authenticated_client,
        "record_sale",
        {"amount": "500.00", "party": "Mary Otieno"},
    )

    assert response.data["status"] == "executed"
    assert Transaction.objects.get().party.name == "Mary Otieno"


def test_a_party_owing_in_both_directions_is_asked_about(
    authenticated_client, business, user, customer
):
    from apps.debts.models import DebtType
    from apps.debts.services import create_debt

    for debt_type in (DebtType.RECEIVABLE, DebtType.PAYABLE):
        create_debt(
            business=business,
            created_by=user,
            debt_type=debt_type,
            party=customer,
            original_amount=Decimal("500.00"),
        )

    response = call(
        authenticated_client,
        "record_debt_payment",
        {"party": "Mary", "amount": "100.00"},
    )

    assert response.data["status"] == "clarification_required"
    assert "paying you" in response.data["message"]


def test_direction_settles_the_ambiguity(
    authenticated_client, business, user, customer
):
    from apps.debts.models import DebtType
    from apps.debts.services import create_debt

    for debt_type in (DebtType.RECEIVABLE, DebtType.PAYABLE):
        create_debt(
            business=business,
            created_by=user,
            debt_type=debt_type,
            party=customer,
            original_amount=Decimal("500.00"),
        )

    response = call(
        authenticated_client,
        "record_debt_payment",
        {"party": "Mary", "amount": "100.00", "direction": "receivable"},
    )

    assert response.data["status"] == "executed"
    assert "received from Mary Wanjiku" in response.data["message"]
