"""
The only place transactions are written.

Views, and later the AI agent tools, both go through these functions so that a
spoken transaction is validated exactly like a typed one.
"""

from decimal import Decimal

from django.db import transaction as db_transaction

from apps.ledger.models import PaymentStatus, Transaction

ZERO = Decimal("0.00")


class LedgerRuleViolation(Exception):
    """Raised when a transaction would be financially inconsistent."""


def resolve_payment(amount: Decimal, payment_status: str | None, amount_paid=None):
    """
    Reconciles the payment status with the amount actually settled.

    Clients may send either — "this was paid" or "they gave me 500 of the 2,000"
    — so whichever is missing is derived, and a contradiction is rejected rather
    than silently corrected.
    """
    if payment_status is None and amount_paid is None:
        return PaymentStatus.PAID, amount

    if amount_paid is None:
        if payment_status == PaymentStatus.PAID:
            return PaymentStatus.PAID, amount
        if payment_status == PaymentStatus.CREDIT:
            return PaymentStatus.CREDIT, ZERO
        raise LedgerRuleViolation(
            "A partially paid transaction must say how much was paid."
        )

    amount_paid = Decimal(amount_paid)

    if amount_paid < ZERO:
        raise LedgerRuleViolation("Amount paid cannot be negative.")
    if amount_paid > amount:
        raise LedgerRuleViolation("Amount paid cannot exceed the transaction amount.")

    derived = (
        PaymentStatus.PAID
        if amount_paid == amount
        else PaymentStatus.CREDIT
        if amount_paid == ZERO
        else PaymentStatus.PARTIAL
    )

    if payment_status is not None and payment_status != derived:
        raise LedgerRuleViolation(
            f"Amount paid of {amount_paid} does not match a status of '{payment_status}'."
        )

    return derived, amount_paid


def resolve_amount(amount=None, quantity=None, unit_price=None) -> Decimal:
    """
    Works out the total when only the parts are known.

    "Two crates at 1,200" is a natural way to speak a sale, so the total is
    derived rather than demanded.
    """
    if amount is not None:
        return Decimal(amount)

    if quantity is not None and unit_price is not None:
        return (Decimal(quantity) * Decimal(unit_price)).quantize(Decimal("0.01"))

    raise LedgerRuleViolation(
        "Provide an amount, or a quantity and unit price to calculate it from."
    )


@db_transaction.atomic
def record_transaction(*, business, created_by=None, **fields) -> Transaction:
    """Creates a transaction after normalising its money fields."""
    amount = resolve_amount(
        amount=fields.pop("amount", None),
        quantity=fields.get("quantity"),
        unit_price=fields.get("unit_price"),
    )
    payment_status, amount_paid = resolve_payment(
        amount,
        fields.pop("payment_status", None),
        fields.pop("amount_paid", None),
    )

    fields.setdefault("currency", business.currency)

    return Transaction.objects.create(
        business=business,
        created_by=created_by,
        amount=amount,
        payment_status=payment_status,
        amount_paid=amount_paid,
        **fields,
    )


@db_transaction.atomic
def update_transaction(instance: Transaction, **fields) -> Transaction:
    """
    Applies a correction to an existing transaction.

    Corrections are allowed because misheard amounts are the most common voice
    failure, and a trader must be able to fix "24,000" back to "2,400".
    """
    status_given = "payment_status" in fields
    paid_given = "amount_paid" in fields

    for field, value in fields.items():
        setattr(instance, field, value)

    if "amount" not in fields and any(key in fields for key in ("quantity", "unit_price")):
        instance.amount = resolve_amount(
            quantity=instance.quantity, unit_price=instance.unit_price
        )

    if status_given or paid_given:
        # Whichever the client supplied wins; the other is derived from it.
        status = fields.get("payment_status") if status_given else None
        paid = fields.get("amount_paid") if paid_given else None
    else:
        # Nothing about payment changed, but the amount may have. A fully paid
        # transaction stays fully paid at its corrected amount.
        status = instance.payment_status
        paid = None if status in (PaymentStatus.PAID, PaymentStatus.CREDIT) else instance.amount_paid

    instance.payment_status, instance.amount_paid = resolve_payment(
        instance.amount, status, paid
    )

    instance.full_clean(exclude=["business", "created_by"])
    instance.save()
    return instance
