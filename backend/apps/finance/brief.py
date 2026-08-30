"""
The daily brief: the numbers said back in ordinary language.

No model writes this. Every sentence is assembled from figures the selectors
calculated, which is what makes it safe to speak aloud — the voice layer in a
later phase reads these lines rather than inventing its own.

Each line is tagged `fact` or `estimate`. A number that came from arithmetic on
recorded transactions and a number that depends on customers behaving as
promised are not the same kind of claim, and a trader deciding whether to buy
stock tomorrow deserves to know which one they are hearing.
"""

from decimal import Decimal

from django.utils import timezone

from apps.finance import selectors
from apps.finance.periods import Period

FACT = "fact"
ESTIMATE = "estimate"

ZERO = Decimal("0.00")


def format_money(amount: Decimal, currency: str) -> str:
    """Formats money the way it gets spoken: grouped, and without idle cents."""
    quantised = Decimal(amount).quantize(Decimal("0.01"))
    whole = quantised == quantised.to_integral_value()
    return f"{currency} {quantised:,.0f}" if whole else f"{currency} {quantised:,.2f}"


def daily_brief(business) -> dict:
    today = timezone.localdate()
    cash = selectors.cash_position(business)
    trading = selectors.summary(business, Period("today", today, today))
    risk = selectors.float_risk(business)

    currency = business.currency
    money = lambda amount: format_money(amount, currency)  # noqa: E731

    messages = [
        {"kind": FACT, "text": f"You have {money(cash['available_cash'])} available."}
    ]

    if trading["transaction_count"] == 0:
        messages.append({"kind": FACT, "text": "Nothing has been recorded today yet."})
    else:
        messages.append(
            {
                "kind": FACT,
                "text": (
                    f"Today you took in {money(trading['cash_in'])} and spent "
                    f"{money(trading['cash_out'])} across "
                    f"{trading['transaction_count']} "
                    f"{'entry' if trading['transaction_count'] == 1 else 'entries'}."
                ),
            }
        )

    if cash["receivables"] > ZERO:
        line = f"Customers owe you {money(cash['receivables'])}."
        if cash["receivables_overdue"] > ZERO:
            line += f" {money(cash['receivables_overdue'])} of that is already late."
        messages.append({"kind": FACT, "text": line})

    if cash["payables"] > ZERO:
        line = f"You owe {money(cash['payables'])}."
        if cash["payables_overdue"] > ZERO:
            line += f" {money(cash['payables_overdue'])} of that is already late."
        messages.append({"kind": FACT, "text": line})

    messages.append(_float_message(risk, money))

    return {
        "currency": currency,
        "generated_at": timezone.now(),
        "headline": messages[0]["text"],
        "messages": messages,
        "cash_position": cash,
        "today": trading,
        "float_risk": risk,
    }


def _float_message(risk: dict, money) -> dict:
    """The one line that changes what a trader does next."""
    days = risk["horizon_days"]

    if risk["obligations_due"] == ZERO:
        return {
            "kind": FACT,
            "text": f"Nothing is due in the next {days} days.",
        }

    if risk["risk_level"] == "none":
        return {
            "kind": FACT,
            "text": (
                f"You have {money(risk['obligations_due'])} due in the next {days} "
                f"days, and enough cash to cover it."
            ),
        }

    if risk["risk_level"] == "watch":
        return {
            "kind": ESTIMATE,
            "text": (
                f"You may be short by about {money(risk['shortfall'])} in the next "
                f"{days} days, unless the {money(risk['expected_receipts'])} owed to "
                f"you comes in first."
            ),
        }

    return {
        "kind": ESTIMATE,
        "text": (
            f"You are likely to be short by about {money(risk['shortfall'])} in the "
            f"next {days} days, even if everyone who owes you pays."
        ),
    }
