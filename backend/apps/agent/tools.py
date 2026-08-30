"""
The tools themselves.

Each one is a thin translation from words to an existing domain service: the
parameters a person would speak, resolved into records, handed to the same
`record_transaction` or `record_payment` the REST API uses. No tool writes to a
model directly, so a spoken sale is validated exactly like a typed one and there
is no second, weaker path into the ledger.

Every tool splits into two halves. `prepare` turns names into records and may ask
a question; the handler writes. Keeping them apart is what lets Sokoni decide
whether to confirm — a decision that needs the resolved records — and then walk
away without having written anything.
"""

from decimal import Decimal

from rest_framework import serializers

from apps.agent.registry import (
    Clarification,
    ToolError,
    ToolResult,
    register,
)
from apps.agent.resolvers import resolve_party, resolve_product
from apps.debts.models import Debt, DebtStatus, DebtType
from apps.debts.services import DebtRuleViolation, create_debt, record_payment
from apps.finance import selectors
from apps.finance.brief import daily_brief, float_message, format_money
from apps.finance.periods import UnknownPeriod, resolve_period
from apps.ledger.models import (
    PaymentMethod,
    PaymentStatus,
    TransactionSource,
    TransactionType,
)
from apps.ledger.services import LedgerRuleViolation, record_transaction
from apps.parties.models import Party, PartyType


class MoneyParam(serializers.DecimalField):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 12)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("min_value", Decimal("0.01"))
        super().__init__(**kwargs)


def find_party(context, name: str) -> Party:
    """
    Looks a party up without creating one.

    Used by the tools that only ask questions. A question must never leave a
    record behind, so "how much does Maggie owe me" cannot invent a Maggie.
    """
    parties = Party.objects.filter(business=context.business, is_active=True)

    exact = parties.filter(name__iexact=name).first()
    if exact is not None:
        return exact

    partial = list(parties.filter(name__icontains=name)[:6])
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        options = [party.name for party in partial]
        raise Clarification(
            f"Which one did you mean: {', '.join(options[:-1])} or {options[-1]}?",
            options=options,
        )

    raise ToolError(f"Nobody called {name} has traded here.")


# --------------------------------------------------------------------------- #
# Recording money
# --------------------------------------------------------------------------- #


class TradeParams(serializers.Serializer):
    """Shared shape for the four ways money moves."""

    amount = MoneyParam(
        required=False,
        allow_null=True,
        help_text="Total amount. May be omitted if quantity and unit price are given.",
    )
    quantity = serializers.DecimalField(
        max_digits=12,
        decimal_places=3,
        required=False,
        allow_null=True,
        help_text="How many units, when the total was not stated.",
    )
    unit_price = MoneyParam(
        required=False, allow_null=True, help_text="Price per unit."
    )
    party = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Name of the customer or supplier, as spoken.",
    )
    product = serializers.CharField(
        required=False, allow_blank=True, help_text="Name of the item traded."
    )
    payment_status = serializers.ChoiceField(
        choices=PaymentStatus.choices,
        required=False,
        help_text="paid, partial or credit. Defaults to paid.",
    )
    amount_paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0.00"),
        help_text="How much changed hands, for a part payment.",
    )
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices,
        required=False,
        help_text="cash, mpesa, bank, credit or other.",
    )
    description = serializers.CharField(
        required=False, allow_blank=True, help_text="What the entry was for."
    )

    def validate(self, attrs):
        has_parts = attrs.get("quantity") is not None and attrs.get("unit_price") is not None
        if attrs.get("amount") is None and not has_parts:
            raise serializers.ValidationError(
                "Give an amount, or a quantity and a unit price."
            )
        return attrs


def prepare_trade(context, params: dict, *, party_type: str) -> dict:
    prepared = dict(params)

    if params.get("party"):
        party, created = resolve_party(
            context.business, params["party"], party_type=party_type
        )
        prepared["party"] = party
        if created:
            prepared["_new_party"] = party.name
    else:
        prepared.pop("party", None)

    if params.get("product"):
        product, _ = resolve_product(context.business, params["product"])
        prepared["product"] = product
    else:
        prepared.pop("product", None)

    return prepared


def trade_phrase(context, params: dict, *, noun: str, preposition: str) -> str:
    amount = params.get("amount")
    if amount is None and params.get("quantity") and params.get("unit_price"):
        amount = Decimal(params["quantity"]) * Decimal(params["unit_price"])

    phrase = f"a {noun} of {format_money(amount or 0, context.business.currency)}"

    name = getattr(params.get("party"), "name", params.get("party"))
    if name:
        phrase += f" {preposition} {name}"

    if params.get("payment_status") == PaymentStatus.CREDIT:
        phrase += " on credit"

    return phrase


def record_trade(
    context, params: dict, *, transaction_type: str, noun: str, preposition: str
) -> ToolResult:
    from apps.ledger.serializers import TransactionSerializer

    fields = {
        key: value
        for key, value in params.items()
        if not key.startswith("_") and value is not None and value != ""
    }
    fields["transaction_type"] = transaction_type
    fields.setdefault("source", TransactionSource.VOICE)

    try:
        transaction = record_transaction(
            business=context.business, created_by=context.user, **fields
        )
    except LedgerRuleViolation as exc:
        raise ToolError(str(exc)) from exc

    currency = transaction.currency
    message = f"Recorded a {noun} of {format_money(transaction.amount, currency)}"

    if transaction.party:
        message += f" {preposition} {transaction.party.name}"
    if transaction.outstanding_amount > 0:
        message += (
            f", with {format_money(transaction.outstanding_amount, currency)} still owed"
        )

    return ToolResult(
        message=f"{message}.",
        data=TransactionSerializer(transaction).data,
        created=True,
    )


@register(
    name="record_sale",
    description="Record something sold, paid for now or taken on credit.",
    parameters=TradeParams,
    mutating=True,
    prepare=lambda context, params: prepare_trade(
        context, params, party_type=PartyType.CUSTOMER
    ),
    phrase=lambda context, params: trade_phrase(
        context, params, noun="sale", preposition="to"
    ),
)
def record_sale(context, params):
    return record_trade(
        context,
        params,
        transaction_type=TransactionType.SALE,
        noun="sale",
        preposition="to",
    )


@register(
    name="record_income",
    description="Record money received that is not a sale of goods.",
    parameters=TradeParams,
    mutating=True,
    prepare=lambda context, params: prepare_trade(
        context, params, party_type=PartyType.CUSTOMER
    ),
    phrase=lambda context, params: trade_phrase(
        context, params, noun="payment received", preposition="from"
    ),
)
def record_income(context, params):
    return record_trade(
        context,
        params,
        transaction_type=TransactionType.INCOME,
        noun="payment received",
        preposition="from",
    )


@register(
    name="record_purchase",
    description="Record stock or goods bought for the business.",
    parameters=TradeParams,
    mutating=True,
    prepare=lambda context, params: prepare_trade(
        context, params, party_type=PartyType.SUPPLIER
    ),
    phrase=lambda context, params: trade_phrase(
        context, params, noun="purchase", preposition="from"
    ),
)
def record_purchase(context, params):
    return record_trade(
        context,
        params,
        transaction_type=TransactionType.PURCHASE,
        noun="purchase",
        preposition="from",
    )


@register(
    name="record_expense",
    description="Record money spent running the business.",
    parameters=TradeParams,
    mutating=True,
    prepare=lambda context, params: prepare_trade(
        context, params, party_type=PartyType.SUPPLIER
    ),
    phrase=lambda context, params: trade_phrase(
        context, params, noun="expense", preposition="to"
    ),
)
def record_expense(context, params):
    return record_trade(
        context,
        params,
        transaction_type=TransactionType.EXPENSE,
        noun="expense",
        preposition="to",
    )


# --------------------------------------------------------------------------- #
# Recording debt
# --------------------------------------------------------------------------- #


class DebtParams(serializers.Serializer):
    party = serializers.CharField(help_text="Who the debt is with, as spoken.")
    amount = MoneyParam(help_text="How much is owed.")
    due_date = serializers.DateField(
        required=False, allow_null=True, help_text="When it was promised, if said."
    )
    description = serializers.CharField(
        required=False, allow_blank=True, help_text="What the debt was for."
    )


def prepare_debt(context, params: dict, *, party_type: str) -> dict:
    prepared = dict(params)
    party, created = resolve_party(
        context.business, params["party"], party_type=party_type
    )
    prepared["party"] = party
    if created:
        prepared["_new_party"] = party.name
    return prepared


def create_debt_entry(context, params: dict, *, debt_type: str) -> ToolResult:
    from apps.debts.serializers import DebtSerializer

    try:
        debt = create_debt(
            business=context.business,
            created_by=context.user,
            debt_type=debt_type,
            party=params["party"],
            original_amount=params["amount"],
            due_date=params.get("due_date"),
            description=params.get("description") or "",
            source=TransactionSource.VOICE,
        )
    except DebtRuleViolation as exc:
        raise ToolError(str(exc)) from exc

    money = format_money(debt.original_amount, debt.currency)
    if debt_type == DebtType.RECEIVABLE:
        message = f"Recorded that {debt.party.name} owes you {money}"
    else:
        message = f"Recorded that you owe {debt.party.name} {money}"
    if debt.due_date:
        message += f", due {debt.due_date.isoformat()}"

    return ToolResult(
        message=f"{message}.", data=DebtSerializer(debt).data, created=True
    )


def debt_phrase(context, params: dict, *, owed_to_business: bool) -> str:
    money = format_money(params.get("amount") or 0, context.business.currency)
    name = getattr(params.get("party"), "name", params.get("party"))
    if owed_to_business:
        return f"a debt of {money} owed to you by {name}"
    return f"a debt of {money} that you owe {name}"


@register(
    name="create_receivable",
    description="Record that someone owes the business money.",
    parameters=DebtParams,
    mutating=True,
    prepare=lambda context, params: prepare_debt(
        context, params, party_type=PartyType.CUSTOMER
    ),
    phrase=lambda context, params: debt_phrase(
        context, params, owed_to_business=True
    ),
)
def create_receivable(context, params):
    return create_debt_entry(context, params, debt_type=DebtType.RECEIVABLE)


@register(
    name="create_payable",
    description="Record that the business owes someone money.",
    parameters=DebtParams,
    mutating=True,
    prepare=lambda context, params: prepare_debt(
        context, params, party_type=PartyType.SUPPLIER
    ),
    phrase=lambda context, params: debt_phrase(
        context, params, owed_to_business=False
    ),
)
def create_payable(context, params):
    return create_debt_entry(context, params, debt_type=DebtType.PAYABLE)


class DebtPaymentParams(serializers.Serializer):
    party = serializers.CharField(help_text="Who paid, or who was paid.")
    amount = MoneyParam(help_text="How much was handed over.")
    direction = serializers.ChoiceField(
        choices=DebtType.choices,
        required=False,
        help_text=(
            "receivable when a customer pays you, payable when you pay a supplier. "
            "Inferred when the party only owes in one direction."
        ),
    )
    payment_method = serializers.ChoiceField(
        choices=PaymentMethod.choices, required=False, help_text="How it was paid."
    )


def prepare_debt_payment(context, params: dict) -> dict:
    """
    Finds the single debt a payment belongs to.

    Applying money to the wrong obligation is a mistake that compounds every time
    a balance is read afterwards, so a party owing in both directions at once is a
    question rather than a guess.
    """
    prepared = dict(params)
    party = find_party(context, params["party"])
    prepared["party"] = party

    debts = Debt.objects.filter(
        business=context.business, party=party, is_active=True
    ).outstanding()

    if params.get("direction"):
        debts = debts.filter(debt_type=params["direction"])

    candidates = list(debts.order_by("due_date", "created_at")[:6])

    if not candidates:
        raise ToolError(f"{party.name} has no outstanding debt to settle.")

    if len({debt.debt_type for debt in candidates}) > 1:
        raise Clarification(
            f"Is {party.name} paying you, or are you paying {party.name}?",
            options=[DebtType.RECEIVABLE, DebtType.PAYABLE],
        )

    # Oldest due first: the debt that has been waiting longest is the one a
    # payment is normally meant for.
    prepared["debt"] = candidates[0]
    return prepared


def payment_phrase(context, params: dict) -> str:
    money = format_money(params.get("amount") or 0, context.business.currency)
    name = getattr(params.get("party"), "name", params.get("party"))
    debt = params.get("debt")

    if debt is None:
        return f"a payment of {money} involving {name}"
    if debt.debt_type == DebtType.RECEIVABLE:
        return f"a payment of {money} received from {name}"
    return f"a payment of {money} paid to {name}"


@register(
    name="record_debt_payment",
    description="Record an instalment against a debt, in either direction.",
    parameters=DebtPaymentParams,
    mutating=True,
    prepare=prepare_debt_payment,
    phrase=payment_phrase,
)
def record_debt_payment(context, params):
    from apps.debts.serializers import DebtSerializer

    debt = params["debt"]
    try:
        record_payment(
            debt,
            amount=params["amount"],
            created_by=context.user,
            payment_method=params.get("payment_method") or PaymentMethod.CASH,
            source=TransactionSource.VOICE,
        )
    except DebtRuleViolation as exc:
        raise ToolError(str(exc)) from exc

    debt.refresh_from_db()
    money = format_money(params["amount"], debt.currency)
    who = debt.party.name

    if debt.debt_type == DebtType.RECEIVABLE:
        message = f"Recorded {money} received from {who}"
    else:
        message = f"Recorded {money} paid to {who}"

    if debt.status == DebtStatus.SETTLED:
        message += ", clearing the debt"
    else:
        message += f", leaving {format_money(debt.balance, debt.currency)} owed"

    return ToolResult(
        message=f"{message}.", data=DebtSerializer(debt).data, created=True
    )


# --------------------------------------------------------------------------- #
# Answering questions
# --------------------------------------------------------------------------- #


class NoParams(serializers.Serializer):
    pass


class PeriodParams(serializers.Serializer):
    period = serializers.CharField(
        required=False,
        help_text="today, yesterday, week, month, year or all. Defaults to today.",
    )
    date_from = serializers.DateField(
        required=False, allow_null=True, help_text="Start of a custom range."
    )
    date_to = serializers.DateField(
        required=False, allow_null=True, help_text="End of a custom range."
    )


@register(
    name="get_cash_position",
    description="What the business holds now, and what is owed in each direction.",
    parameters=NoParams,
)
def get_cash_position(context, params):
    from apps.finance.serializers import CashPositionSerializer

    data = selectors.cash_position(context.business)
    return ToolResult(
        message=f"You have {format_money(data['available_cash'], data['currency'])} available.",
        data=CashPositionSerializer(data).data,
    )


@register(
    name="get_summary",
    description="Revenue, costs and cash movement over a period.",
    parameters=PeriodParams,
)
def get_summary(context, params):
    from apps.finance.serializers import SummarySerializer

    try:
        period = resolve_period(
            {key: str(value) for key, value in params.items() if value is not None}
        )
    except UnknownPeriod as exc:
        raise ToolError(str(exc)) from exc

    data = selectors.summary(context.business, period)
    currency = data["currency"]

    return ToolResult(
        message=(
            f"{_period_words(period.label)} you took in "
            f"{format_money(data['revenue'], currency)} and spent "
            f"{format_money(data['expenses'], currency)}, leaving an estimated "
            f"{format_money(data['profit_estimate'], currency)}."
        ),
        data=SummarySerializer(data).data,
    )


def _period_words(label: str) -> str:
    return {
        "today": "Today",
        "yesterday": "Yesterday",
        "week": "Over the last seven days",
        "month": "This month",
        "year": "This year",
        "all": "In total",
    }.get(label, "Over that period")


@register(
    name="check_float_risk",
    description="Whether the business can meet what falls due soon.",
    parameters=NoParams,
)
def check_float_risk(context, params):
    from apps.finance.serializers import FloatRiskSerializer

    data = selectors.float_risk(context.business)
    spoken = float_message(data, lambda amount: format_money(amount, data["currency"]))

    return ToolResult(message=spoken["text"], data=FloatRiskSerializer(data).data)


@register(
    name="get_daily_brief",
    description="The whole financial picture, in sentences that can be read aloud.",
    parameters=NoParams,
)
def get_daily_brief(context, params):
    from apps.finance.serializers import DailyBriefSerializer

    data = daily_brief(context.business)
    return ToolResult(
        message=" ".join(message["text"] for message in data["messages"]),
        data=DailyBriefSerializer(data).data,
    )


class PartyBalanceParams(serializers.Serializer):
    party = serializers.CharField(help_text="Whose balance to check, as spoken.")


@register(
    name="get_party_balance",
    description="How much one customer or supplier owes, or is owed.",
    parameters=PartyBalanceParams,
)
def get_party_balance(context, params):
    from apps.finance.serializers import PartyBalanceSerializer

    party = find_party(context, params["party"])
    data = selectors.party_balance(context.business, party)
    currency = data["currency"]

    if data["net_balance"] > 0:
        message = f"{party.name} owes you {format_money(data['net_balance'], currency)}"
        if data["overdue"] > 0:
            message += f", and {format_money(data['overdue'], currency)} of it is late"
    elif data["net_balance"] < 0:
        message = f"You owe {party.name} {format_money(-data['net_balance'], currency)}"
    else:
        message = f"You and {party.name} are settled up"

    return ToolResult(
        message=f"{message}.", data=PartyBalanceSerializer(data).data
    )


class DebtQueryParams(serializers.Serializer):
    direction = serializers.ChoiceField(
        choices=DebtType.choices,
        required=False,
        help_text="receivable for money owed to you, payable for money you owe.",
    )
    overdue_only = serializers.BooleanField(
        required=False, help_text="Only debts already past their due date."
    )


@register(
    name="get_debts",
    description="Who owes the business money, and who the business owes.",
    parameters=DebtQueryParams,
)
def get_debts(context, params):
    from apps.debts.serializers import DebtSerializer

    debts = (
        Debt.objects.filter(business=context.business, is_active=True)
        .outstanding()
        .select_related("party")
    )
    if params.get("direction"):
        debts = debts.filter(debt_type=params["direction"])
    if params.get("overdue_only"):
        debts = debts.overdue()

    debts = list(debts[:50])
    currency = context.business.currency

    if not debts:
        return ToolResult(message="There are no outstanding debts.", data=[])

    named = ", ".join(
        f"{debt.party.name} {format_money(debt.balance, currency)}"
        for debt in debts[:5]
    )
    total = sum((debt.balance for debt in debts), Decimal("0.00"))
    message = f"{len(debts)} outstanding, {format_money(total, currency)} in total: {named}"
    if len(debts) > 5:
        message += ", and others"

    return ToolResult(message=f"{message}.", data=DebtSerializer(debts, many=True).data)


class RecentTransactionParams(serializers.Serializer):
    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=50,
        help_text="How many entries to return. Defaults to 5.",
    )


@register(
    name="get_recent_transactions",
    description="The most recent entries in the ledger.",
    parameters=RecentTransactionParams,
)
def get_recent_transactions(context, params):
    from apps.ledger.models import Transaction
    from apps.ledger.serializers import TransactionSerializer

    limit = params.get("limit") or 5
    transactions = list(
        Transaction.objects.filter(business=context.business)
        .active()
        .select_related("party", "product")[:limit]
    )

    if not transactions:
        return ToolResult(message="Nothing has been recorded yet.", data=[])

    spoken = ", ".join(
        f"{transaction.get_transaction_type_display().lower()} "
        f"{format_money(transaction.amount, transaction.currency)}"
        for transaction in transactions
    )
    return ToolResult(
        message=f"The last {len(transactions)}: {spoken}.",
        data=TransactionSerializer(transactions, many=True).data,
    )
