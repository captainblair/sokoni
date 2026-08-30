"""
Read-only financial calculations.

Where a `services` module is the only place a model is written, a `selectors`
module is the only place numbers are derived. Nothing here is stored: a cash
position saved to a column is a cash position that will eventually disagree with
the transactions behind it.

Two ideas run through every figure below and are worth stating plainly:

*Accrual* asks what the business earned — a sale is revenue the moment it
happens, paid or not. *Cash* asks what the business can actually spend today.
Informal traders live by the second and are judged by the first, so both are
reported, separately and never blended.
"""

from datetime import timedelta
from decimal import Decimal
from statistics import median

from django.db.models import Count, DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.debts.models import Debt, DebtPayment, DebtType
from apps.ledger.models import Transaction

ZERO = Decimal("0.00")
MONEY = DecimalField(max_digits=14, decimal_places=2)

#: How far ahead "upcoming obligations" looks by default.
DEFAULT_HORIZON_DAYS = 7


def _sum(queryset, expression) -> Decimal:
    total = queryset.aggregate(
        total=Coalesce(Sum(expression, output_field=MONEY), Value(ZERO), output_field=MONEY)
    )["total"]
    return Decimal(total).quantize(Decimal("0.01"))


def _transactions(business):
    return Transaction.objects.filter(business=business).active()


def _debts(business):
    return Debt.objects.filter(business=business, is_active=True)


def _standalone_debt_payments(business):
    """
    Payments against debts that never came from a transaction.

    A debt created from a credit sale mirrors its payments back onto that
    transaction, so counting both would double the money. A debt entered on its
    own — "John has owed me 2,000 since before I started using this" — has no
    transaction behind it, making its payments the only record of that cash.
    """
    return DebtPayment.objects.filter(
        debt__business=business,
        debt__is_active=True,
        debt__source_transaction__isnull=True,
    )


def cash_position(business) -> dict:
    """What the business holds now, and what is still owed in each direction."""
    transactions = _transactions(business)
    debt_payments = _standalone_debt_payments(business)

    collected = _sum(transactions.money_in(), "amount_paid") + _sum(
        debt_payments.filter(debt__debt_type=DebtType.RECEIVABLE), "amount"
    )
    paid_out = _sum(transactions.money_out(), "amount_paid") + _sum(
        debt_payments.filter(debt__debt_type=DebtType.PAYABLE), "amount"
    )

    receivable = _outstanding(business, DebtType.RECEIVABLE)
    payable = _outstanding(business, DebtType.PAYABLE)

    available = collected - paid_out
    return {
        "currency": business.currency,
        "available_cash": available,
        "cash_in": collected,
        "cash_out": paid_out,
        "receivables": receivable["total"],
        "receivables_overdue": receivable["overdue"],
        "payables": payable["total"],
        "payables_overdue": payable["overdue"],
        # What the business would hold if every debt in both directions settled.
        "projected_cash": available + receivable["total"] - payable["total"],
        "as_of": timezone.now(),
    }


def _outstanding(business, debt_type: str) -> dict:
    """
    Everything still owed in one direction.

    Debts are the tracked half. The other half is a credit transaction recorded
    without naming anyone: nobody to chase, but the money is owed all the same,
    and leaving it out would flatter the numbers.
    """
    debts = _debts(business).filter(debt_type=debt_type).outstanding()
    tracked = _sum(debts, F("original_amount") - F("amount_paid"))

    untracked_source = (
        _transactions(business).money_in()
        if debt_type == DebtType.RECEIVABLE
        else _transactions(business).money_out()
    )
    # Excluding by active debt rather than by the absence of one: a debt archived
    # as a mistake must not take the underlying transaction's balance with it.
    untracked = _sum(
        untracked_source.unsettled().exclude(debt__is_active=True),
        F("amount") - F("amount_paid"),
    )

    return {
        "total": tracked + untracked,
        "tracked": tracked,
        "untracked": untracked,
        "overdue": _sum(debts.overdue(), F("original_amount") - F("amount_paid")),
        "count": debts.count(),
    }


def party_balance(business, party) -> dict:
    """
    Where one person stands with the business.

    Answering "how much does John owe me?" has to net both directions, because a
    customer who also supplies goods is one relationship, not two.
    """
    debts = _debts(business).filter(party=party).outstanding()
    balance = F("original_amount") - F("amount_paid")

    owed_to_business = _sum(debts.receivables(), balance)
    owed_by_business = _sum(debts.payables(), balance)

    untracked = (
        _transactions(business)
        .filter(party=party)
        .unsettled()
        .exclude(debt__is_active=True)
    )
    owed_to_business += _sum(untracked.money_in(), F("amount") - F("amount_paid"))
    owed_by_business += _sum(untracked.money_out(), F("amount") - F("amount_paid"))

    return {
        "currency": business.currency,
        "party": party.name,
        "owed_to_business": owed_to_business,
        "owed_by_business": owed_by_business,
        "net_balance": owed_to_business - owed_by_business,
        "overdue": _sum(debts.overdue(), balance),
        "open_debts": debts.count(),
    }


def summary(business, period) -> dict:
    """Revenue, costs and cash movement over a period."""
    transactions = _transactions(business).in_period(period.start, period.end)
    money_in = transactions.money_in()
    money_out = transactions.money_out()

    revenue = _sum(money_in, "amount")
    expenses = _sum(money_out, "amount")

    debt_payments = _standalone_debt_payments(business)
    if period.start is not None:
        debt_payments = debt_payments.filter(paid_at__gte=period.start)
    if period.end is not None:
        debt_payments = debt_payments.filter(paid_at__lte=period.end)

    cash_in = _sum(money_in, "amount_paid") + _sum(
        debt_payments.filter(debt__debt_type=DebtType.RECEIVABLE), "amount"
    )
    cash_out = _sum(money_out, "amount_paid") + _sum(
        debt_payments.filter(debt__debt_type=DebtType.PAYABLE), "amount"
    )

    return {
        "currency": business.currency,
        "period": period.label,
        "date_from": period.start_date,
        "date_to": period.end_date,
        "revenue": revenue,
        "expenses": expenses,
        # An estimate, not an audited profit: there is no stock valuation,
        # depreciation or owner's drawings in this model, and saying otherwise
        # would dress a useful number up as an accounting truth.
        "profit_estimate": revenue - expenses,
        "cash_in": cash_in,
        "cash_out": cash_out,
        "net_cash_flow": cash_in - cash_out,
        "credit_given": _sum(
            money_in.unsettled(), F("amount") - F("amount_paid")
        ),
        "credit_taken": _sum(
            money_out.unsettled(), F("amount") - F("amount_paid")
        ),
        "transaction_count": transactions.count(),
        "by_type": _grouped(transactions, "transaction_type"),
        # Grouped on what was actually settled, not what was billed: a credit
        # sale has no payment method yet, and counting it as cash would describe
        # money that never arrived.
        "by_payment_method": _grouped(
            transactions.filter(amount_paid__gt=ZERO), "payment_method", "amount_paid"
        ),
    }


def typical_transaction_amount(
    business, *, days: int = 90, minimum_sample: int = 5
) -> Decimal | None:
    """
    The size of an ordinary transaction for this business.

    The median rather than the mean, because one wholesale purchase should not
    redefine what "ordinary" means for a trader who otherwise sells in hundreds.
    Returns nothing when there is too little history to make the comparison
    honest — a claim about what is normal needs evidence of normal.
    """
    since = timezone.now() - timedelta(days=days)
    amounts = list(
        _transactions(business)
        .in_period(since, None)
        .order_by("-occurred_at")
        .values_list("amount", flat=True)[:500]
    )

    if len(amounts) < minimum_sample:
        return None
    return Decimal(median(amounts)).quantize(Decimal("0.01"))


def _grouped(queryset, field: str, amount_field: str = "amount") -> list[dict]:
    rows = (
        queryset.values(field)
        .annotate(
            total=Coalesce(
                Sum(amount_field, output_field=MONEY), Value(ZERO), output_field=MONEY
            ),
            count=Count("id"),
        )
        .order_by("-total")
    )
    return [
        {
            "key": row[field],
            "total": Decimal(row["total"]).quantize(Decimal("0.01")),
            "count": row["count"],
        }
        for row in rows
    ]


def float_risk(business, horizon_days: int = DEFAULT_HORIZON_DAYS) -> dict:
    """
    Whether the business can meet what falls due soon.

    This is the question that actually matters day to day. A profitable week is
    no comfort if the supplier arrives on Tuesday and the money is sitting in
    other people's pockets.
    """
    today = timezone.localdate()
    horizon = today + timedelta(days=horizon_days)

    outstanding = _debts(business).outstanding()
    due_soon = outstanding.filter(due_date__isnull=False, due_date__lte=horizon)

    obligations = _sum(
        due_soon.filter(debt_type=DebtType.PAYABLE),
        F("original_amount") - F("amount_paid"),
    )
    expected_receipts = _sum(
        due_soon.filter(debt_type=DebtType.RECEIVABLE),
        F("original_amount") - F("amount_paid"),
    )
    # Debts nobody put a date on are still real. They are reported apart from the
    # window rather than folded into it, because "sometime" is not a plan.
    undated = outstanding.filter(due_date__isnull=True)
    undated_payables = _sum(
        undated.filter(debt_type=DebtType.PAYABLE),
        F("original_amount") - F("amount_paid"),
    )
    undated_receivables = _sum(
        undated.filter(debt_type=DebtType.RECEIVABLE),
        F("original_amount") - F("amount_paid"),
    )

    available = cash_position(business)["available_cash"]
    shortfall = max(ZERO, obligations - available)

    if shortfall == ZERO:
        level = "none"
    elif shortfall <= expected_receipts:
        # Survivable, but only if customers actually pay on time — which is
        # precisely the assumption informal businesses get burnt by.
        level = "watch"
    else:
        level = "high"

    return {
        "currency": business.currency,
        "horizon_days": horizon_days,
        "as_of": today,
        "available_cash": available,
        "obligations_due": obligations,
        "expected_receipts": expected_receipts,
        "undated_payables": undated_payables,
        "undated_receivables": undated_receivables,
        "projected_balance": available - obligations,
        "shortfall": shortfall,
        "risk_level": level,
        "overdue_payables": _sum(
            outstanding.filter(debt_type=DebtType.PAYABLE).overdue(),
            F("original_amount") - F("amount_paid"),
        ),
        "overdue_receivables": _sum(
            outstanding.filter(debt_type=DebtType.RECEIVABLE).overdue(),
            F("original_amount") - F("amount_paid"),
        ),
    }
