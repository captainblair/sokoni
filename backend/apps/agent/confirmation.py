"""
When Sokoni commits, and when it stops to ask.

A voice interface that silently records whatever it thinks it heard is worse than
a notebook, because a notebook is at least wrong in ways its owner can see. The
rules here are deliberately conservative and deliberately few, so a trader can
learn when to expect a question.

Reads are never confirmed. Writes are confirmed when the interpretation is
shaky — low reported confidence, an amount unlike anything this business trades
in, or a name nobody here has traded with before.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from apps.agent.models import ConfirmationReason, PendingAction
from apps.finance.selectors import typical_transaction_amount


class ConfirmationInvalid(Exception):
    """Raised when a confirmation token cannot be honoured."""


@dataclass(frozen=True)
class Verdict:
    """Whether to commit, and if not, what to ask."""

    required: bool
    reason: str = ""
    question: str = ""


def _settings() -> dict:
    return getattr(settings, "AGENT", {})


def review(tool, context, params: dict, confidence: float | None) -> Verdict:
    """Decides whether an understood instruction may commit immediately."""
    if not tool.mutating:
        return Verdict(required=False)

    phrase = tool.phrase(context, params) if tool.phrase else f"this {tool.name}"
    threshold = _settings().get("CONFIDENCE_THRESHOLD", 0.75)

    if confidence is not None and confidence < threshold:
        return Verdict(
            required=True,
            reason=ConfirmationReason.LOW_CONFIDENCE,
            question=f"Did you mean {phrase}?",
        )

    if _amount_is_unusual(tool, context, params):
        return Verdict(
            required=True,
            reason=ConfirmationReason.UNUSUAL_AMOUNT,
            question=f"That is much larger than usual. Did you mean {phrase}?",
        )

    if params.get("_new_party"):
        return Verdict(
            required=True,
            reason=ConfirmationReason.NEW_PARTY,
            question=(
                f"{params['_new_party']} has not traded here before. "
                f"Should I record {phrase}?"
            ),
        )

    return Verdict(required=False)


def _amount_is_unusual(tool, context, params: dict) -> bool:
    """
    Catches the decimal that slipped.

    "Twenty four hundred" heard as "twenty four thousand" is the characteristic
    speech-to-text failure for money, and it is invisible to schema validation:
    24,000 is a perfectly valid amount. What makes it suspicious is the business
    it was said in, so the comparison is against this trader's own history rather
    than a fixed ceiling that would nag a wholesaler and wave through a kiosk.
    """
    amount = tool.amount(params)
    if amount is None:
        return False

    typical = typical_transaction_amount(context.business)
    if typical is None or typical <= 0:
        # Too little history to judge. Confidence is the only guard that early on.
        return False

    factor = Decimal(str(_settings().get("UNUSUAL_AMOUNT_FACTOR", 5)))
    return amount > typical * factor


def hold(tool, context, raw_parameters: dict, verdict: Verdict, confidence) -> PendingAction:
    """Parks a write until the user answers the question."""
    ttl = _settings().get("CONFIRMATION_TTL_SECONDS", 300)
    return PendingAction.objects.create(
        business=context.business,
        user=context.user,
        token=PendingAction.new_token(),
        tool=tool.name,
        parameters=raw_parameters,
        question=verdict.question,
        reason=verdict.reason,
        confidence=confidence,
        expires_at=timezone.now() + timedelta(seconds=ttl),
    )


def consume(token: str, *, user, business) -> PendingAction:
    """
    Redeems a confirmation exactly once.

    Bound to the user and the business that raised it, so a token is useless
    anywhere else, and single-use so an accidental repeat cannot record a second
    sale that never happened.
    """
    action = PendingAction.objects.filter(token=token).first()

    if action is None or action.user_id != user.id or action.business_id != business.id:
        raise ConfirmationInvalid("That confirmation is not recognised.")
    if action.is_consumed:
        raise ConfirmationInvalid("That confirmation has already been used.")
    if action.is_expired:
        raise ConfirmationInvalid(
            "That confirmation has expired. Please say it again."
        )

    action.consumed_at = timezone.now()
    action.save(update_fields=["consumed_at", "updated_at"])
    return action
