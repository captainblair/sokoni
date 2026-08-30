"""
Output shapes for the finance endpoints.

These serialise dictionaries rather than models, and exist so the response
contract is declared in one place instead of being implied by whatever the
selectors happened to return.
"""

from rest_framework import serializers


class MoneyField(serializers.DecimalField):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", 14)
        kwargs.setdefault("decimal_places", 2)
        kwargs.setdefault("read_only", True)
        super().__init__(**kwargs)


class CashPositionSerializer(serializers.Serializer):
    currency = serializers.CharField(read_only=True)
    available_cash = MoneyField()
    cash_in = MoneyField()
    cash_out = MoneyField()
    receivables = MoneyField()
    receivables_overdue = MoneyField()
    payables = MoneyField()
    payables_overdue = MoneyField()
    projected_cash = MoneyField()
    as_of = serializers.DateTimeField(read_only=True)


class GroupSerializer(serializers.Serializer):
    key = serializers.CharField(read_only=True)
    total = MoneyField()
    count = serializers.IntegerField(read_only=True)


class SummarySerializer(serializers.Serializer):
    currency = serializers.CharField(read_only=True)
    period = serializers.CharField(read_only=True)
    date_from = serializers.DateField(read_only=True, allow_null=True)
    date_to = serializers.DateField(read_only=True, allow_null=True)
    revenue = MoneyField()
    expenses = MoneyField()
    profit_estimate = MoneyField()
    cash_in = MoneyField()
    cash_out = MoneyField()
    net_cash_flow = MoneyField()
    credit_given = MoneyField()
    credit_taken = MoneyField()
    transaction_count = serializers.IntegerField(read_only=True)
    by_type = GroupSerializer(many=True, read_only=True)
    by_payment_method = GroupSerializer(many=True, read_only=True)


class FloatRiskSerializer(serializers.Serializer):
    currency = serializers.CharField(read_only=True)
    horizon_days = serializers.IntegerField(read_only=True)
    as_of = serializers.DateField(read_only=True)
    available_cash = MoneyField()
    obligations_due = MoneyField()
    expected_receipts = MoneyField()
    undated_payables = MoneyField()
    undated_receivables = MoneyField()
    projected_balance = MoneyField()
    shortfall = MoneyField()
    risk_level = serializers.CharField(read_only=True)
    overdue_payables = MoneyField()
    overdue_receivables = MoneyField()


class PartyBalanceSerializer(serializers.Serializer):
    currency = serializers.CharField(read_only=True)
    party = serializers.CharField(read_only=True)
    owed_to_business = MoneyField()
    owed_by_business = MoneyField()
    net_balance = MoneyField()
    overdue = MoneyField()
    open_debts = serializers.IntegerField(read_only=True)


class BriefMessageSerializer(serializers.Serializer):
    kind = serializers.CharField(read_only=True)
    text = serializers.CharField(read_only=True)


class DailyBriefSerializer(serializers.Serializer):
    currency = serializers.CharField(read_only=True)
    generated_at = serializers.DateTimeField(read_only=True)
    headline = serializers.CharField(read_only=True)
    messages = BriefMessageSerializer(many=True, read_only=True)
    cash_position = CashPositionSerializer(read_only=True)
    today = SummarySerializer(read_only=True)
    float_risk = FloatRiskSerializer(read_only=True)
