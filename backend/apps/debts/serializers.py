from rest_framework import serializers

from apps.debts.models import Debt, DebtPayment
from apps.parties.models import Party


class DebtPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DebtPayment
        fields = [
            "id",
            "amount",
            "paid_at",
            "payment_method",
            "notes",
            "source",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("A payment must be greater than zero.")
        return value


class DebtSerializer(serializers.ModelSerializer):
    business = serializers.UUIDField(source="business_id", read_only=True)
    party_name = serializers.CharField(source="party.name", read_only=True)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    days_overdue = serializers.IntegerField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    aging_bucket = serializers.CharField(read_only=True)
    payments = DebtPaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Debt
        fields = [
            "id",
            "business",
            "debt_type",
            "party",
            "party_name",
            "original_amount",
            "amount_paid",
            "balance",
            "currency",
            "status",
            "due_date",
            "days_overdue",
            "is_overdue",
            "aging_bucket",
            "description",
            "notes",
            "source",
            "source_transaction",
            "payments",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "business",
            "amount_paid",
            "balance",
            "currency",
            "status",
            "source_transaction",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        instance = self.instance if isinstance(self.instance, Debt) else None
        business = instance.business if instance else self.context.get("business")
        if business is None:
            return

        self.fields["party"].queryset = Party.objects.filter(
            business=business, is_active=True
        )

    def validate_original_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("A debt must be greater than zero.")

        if self.instance and value < self.instance.amount_paid:
            raise serializers.ValidationError(
                "The amount cannot be less than what has already been paid."
            )

        if (
            self.instance
            and self.instance.source_transaction_id
            and value != self.instance.original_amount
        ):
            raise serializers.ValidationError(
                "This debt came from a transaction. Correct that transaction and "
                "the debt will follow."
            )
        return value


class WriteOffSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")
