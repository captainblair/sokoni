"""
The only place audit events are written.

Called from the same service functions that mutate money, inside the same
database transaction, so a write that rolls back never leaves a ghost of itself
in the trail.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from apps.audit.models import AuditAction, AuditEvent, AuditObjectType


def _jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def snapshot(instance, fields: list[str]) -> dict:
    """A JSON-safe picture of the fields that matter for money."""
    picture = {}
    for field in fields:
        value = getattr(instance, field)
        if hasattr(value, "pk") and field.endswith("_id") is False:
            # Related objects are stored as their id; the name is for reading.
            picture[field] = _jsonable(value.pk) if value is not None else None
            name = getattr(value, "name", None)
            if name:
                picture[f"{field}_name"] = name
        else:
            picture[field] = _jsonable(value)
    return picture


TRANSACTION_FIELDS = [
    "id",
    "transaction_type",
    "amount",
    "amount_paid",
    "payment_status",
    "payment_method",
    "currency",
    "party",
    "description",
    "source",
    "is_active",
]

DEBT_FIELDS = [
    "id",
    "debt_type",
    "original_amount",
    "amount_paid",
    "status",
    "currency",
    "party",
    "due_date",
    "description",
    "source",
    "is_active",
]

PAYMENT_FIELDS = ["id", "amount", "payment_method", "paid_at", "source"]


def record_event(
    *,
    business,
    actor,
    action: str,
    object_type: str,
    object_id,
    summary: str,
    before: dict | None = None,
    after: dict | None = None,
    source: str = "",
    extra: dict | None = None,
) -> AuditEvent:
    return AuditEvent.objects.create(
        business=business,
        actor=actor,
        action=action,
        object_type=object_type,
        object_id=object_id,
        summary=summary,
        before=before,
        after=after,
        source=source or "",
        extra=extra or {},
    )


def record_transaction_event(instance, *, actor, action: str, before=None) -> AuditEvent:
    after = snapshot(instance, TRANSACTION_FIELDS)
    verb = {
        AuditAction.CREATED: "Recorded",
        AuditAction.UPDATED: "Corrected",
        AuditAction.ARCHIVED: "Archived",
    }.get(action, "Changed")
    amount = after.get("amount")
    kind = instance.get_transaction_type_display().lower()
    return record_event(
        business=instance.business,
        actor=actor,
        action=action,
        object_type=AuditObjectType.TRANSACTION,
        object_id=instance.id,
        summary=f"{verb} {kind} of {instance.currency} {amount}",
        before=before,
        after=after,
        source=instance.source,
    )


def record_debt_event(instance, *, actor, action: str, before=None, extra=None) -> AuditEvent:
    after = snapshot(instance, DEBT_FIELDS)
    if action == AuditAction.CREATED:
        if instance.debt_type == "receivable":
            summary = (
                f"Recorded that {instance.party.name} owes "
                f"{instance.currency} {instance.original_amount}"
            )
        else:
            summary = (
                f"Recorded that you owe {instance.party.name} "
                f"{instance.currency} {instance.original_amount}"
            )
    elif action == AuditAction.PAID:
        paid = (extra or {}).get("amount", "")
        summary = f"Recorded a payment of {instance.currency} {paid} against {instance.party.name}"
    elif action == AuditAction.WRITTEN_OFF:
        outstanding = (extra or {}).get("outstanding_when_written_off") or instance.original_amount
        summary = (
            f"Wrote off {instance.currency} {outstanding} owed involving "
            f"{instance.party.name}"
        )
    elif action == AuditAction.ARCHIVED:
        summary = f"Archived debt involving {instance.party.name}"
    else:
        summary = f"Updated debt involving {instance.party.name}"

    return record_event(
        business=instance.business,
        actor=actor,
        action=action,
        object_type=AuditObjectType.DEBT,
        object_id=instance.id,
        summary=summary,
        before=before,
        after=after,
        source=instance.source,
        extra=extra,
    )


def record_payment_event(payment, *, actor, debt_before) -> AuditEvent:
    after = snapshot(payment, PAYMENT_FIELDS)
    after["debt_id"] = str(payment.debt_id)
    after["debt_balance"] = str(payment.debt.balance)
    return record_event(
        business=payment.debt.business,
        actor=actor,
        action=AuditAction.PAID,
        object_type=AuditObjectType.DEBT_PAYMENT,
        object_id=payment.id,
        summary=(
            f"Recorded a payment of {payment.debt.currency} {payment.amount} "
            f"against {payment.debt.party.name}"
        ),
        before=debt_before,
        after=after,
        source=payment.source,
    )
