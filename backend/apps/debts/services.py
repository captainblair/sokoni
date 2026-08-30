"""
The only place debts and their payments are written.

Debts and ledger transactions describe the same obligation from two angles, so
keeping them in step is handled here rather than in views or serializers.
"""

from decimal import Decimal

from django.db import transaction as db_transaction

from apps.debts.models import Debt, DebtPayment, DebtStatus, DebtType
from apps.ledger.models import MONEY_IN_TYPES, PaymentStatus

ZERO = Decimal("0.00")


class DebtRuleViolation(Exception):
    """Raised when an operation would leave a debt inconsistent."""


def debt_type_for_transaction(transaction) -> str:
    """A credit sale means someone owes us; a credit purchase means we owe them."""
    return (
        DebtType.RECEIVABLE
        if transaction.transaction_type in MONEY_IN_TYPES
        else DebtType.PAYABLE
    )


@db_transaction.atomic
def create_debt(*, business, created_by=None, **fields) -> Debt:
    debt = Debt(business=business, created_by=created_by, **fields)
    debt.currency = fields.get("currency") or business.currency

    if debt.amount_paid > debt.original_amount:
        raise DebtRuleViolation("Amount paid cannot exceed the debt amount.")

    debt.status = debt.resolved_status()
    debt.save()
    _audit_debt(debt, actor=created_by, action="created")
    return debt


@db_transaction.atomic
def record_payment(
    debt: Debt, *, amount: Decimal, created_by=None, **fields
) -> DebtPayment:
    """Records an instalment and moves the debt's balance and status with it."""
    amount = Decimal(amount)

    if debt.status == DebtStatus.WRITTEN_OFF:
        raise DebtRuleViolation("This debt has been written off.")
    if amount <= ZERO:
        raise DebtRuleViolation("A payment must be greater than zero.")
    if amount > debt.balance:
        raise DebtRuleViolation(
            f"Payment of {amount} exceeds the outstanding balance of {debt.balance}."
        )

    from apps.audit.services import snapshot, DEBT_FIELDS

    debt_before = snapshot(debt, DEBT_FIELDS)

    payment = DebtPayment.objects.create(
        debt=debt, amount=amount, created_by=created_by, **fields
    )

    debt.amount_paid += amount
    debt.status = debt.resolved_status()
    debt.save(update_fields=["amount_paid", "status", "updated_at"])

    _mirror_to_transaction(debt)

    from apps.audit.services import record_payment_event

    record_payment_event(payment, actor=created_by, debt_before=debt_before)
    return payment


@db_transaction.atomic
def write_off_debt(debt: Debt, *, notes: str = "", actor=None) -> Debt:
    """
    Marks a debt as uncollectable.

    Informal businesses do write debts off, and pretending otherwise would leave
    stale balances distorting every later cash calculation.
    """
    if debt.status == DebtStatus.SETTLED:
        raise DebtRuleViolation("A settled debt cannot be written off.")

    from apps.audit.models import AuditAction
    from apps.audit.services import snapshot, DEBT_FIELDS

    before = snapshot(debt, DEBT_FIELDS)
    outstanding = str(debt.balance)

    debt.status = DebtStatus.WRITTEN_OFF
    if notes:
        debt.notes = f"{debt.notes}\n{notes}".strip()
    debt.save(update_fields=["status", "notes", "updated_at"])
    _audit_debt(
        debt,
        actor=actor,
        action=AuditAction.WRITTEN_OFF,
        before=before,
        extra={"notes": notes, "outstanding_when_written_off": outstanding},
    )
    return debt


def _mirror_to_transaction(debt: Debt) -> None:
    """Keeps the originating transaction's settled amount in step with the debt."""
    transaction = debt.source_transaction
    if transaction is None:
        return

    transaction.amount_paid = min(debt.amount_paid, transaction.amount)
    transaction.payment_status = (
        PaymentStatus.PAID
        if transaction.amount_paid >= transaction.amount
        else PaymentStatus.PARTIAL
        if transaction.amount_paid > ZERO
        else PaymentStatus.CREDIT
    )
    transaction.save(update_fields=["amount_paid", "payment_status", "updated_at"])


@db_transaction.atomic
def sync_debt_for_transaction(transaction) -> Debt | None:
    """
    Creates or updates the debt implied by a transaction.

    Called by the ledger whenever a transaction is recorded or corrected. A
    credit sale to a named customer is a receivable; a credit purchase from a
    named supplier is a payable. Without a party there is nobody to chase, so no
    debt is created.
    """
    debt = getattr(transaction, "debt", None)
    settled = transaction.payment_status == PaymentStatus.PAID

    if debt is None:
        if settled or transaction.party_id is None:
            return None

        return create_debt(
            business=transaction.business,
            created_by=transaction.created_by,
            debt_type=debt_type_for_transaction(transaction),
            party=transaction.party,
            original_amount=transaction.amount,
            amount_paid=transaction.amount_paid,
            currency=transaction.currency,
            description=transaction.description,
            source=transaction.source,
            source_transaction=transaction,
        )

    if debt.status == DebtStatus.WRITTEN_OFF:
        return debt

    if transaction.amount < debt.amount_paid:
        raise DebtRuleViolation(
            "The corrected amount is less than what has already been paid against "
            "this debt."
        )

    from apps.audit.models import AuditAction
    from apps.audit.services import snapshot, DEBT_FIELDS

    before = snapshot(debt, DEBT_FIELDS)
    debt.original_amount = transaction.amount
    debt.party = transaction.party or debt.party
    debt.description = transaction.description
    debt.status = debt.resolved_status()
    debt.save(update_fields=["original_amount", "party", "description", "status", "updated_at"])
    if before != snapshot(debt, DEBT_FIELDS):
        _audit_debt(
            debt,
            actor=transaction.created_by,
            action=AuditAction.UPDATED,
            before=before,
        )
    return debt


@db_transaction.atomic
def archive_debt(debt: Debt, *, actor=None) -> Debt:
    from apps.audit.models import AuditAction
    from apps.audit.services import snapshot, DEBT_FIELDS

    before = snapshot(debt, DEBT_FIELDS)
    debt.archive()
    _audit_debt(debt, actor=actor, action=AuditAction.ARCHIVED, before=before)
    return debt


def _audit_debt(instance, *, actor, action: str, before=None, extra=None) -> None:
    from apps.audit.services import record_debt_event

    record_debt_event(
        instance, actor=actor, action=action, before=before, extra=extra
    )
