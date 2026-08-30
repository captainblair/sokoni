from django.utils import timezone
from rest_framework import serializers

from apps.catalog.models import Product
from apps.ledger.models import Transaction
from apps.ledger.services import LedgerRuleViolation, resolve_amount, resolve_payment
from apps.parties.models import Party


class TransactionSerializer(serializers.ModelSerializer):
    business = serializers.UUIDField(source="business_id", read_only=True)
    party_name = serializers.CharField(source="party.name", read_only=True, default=None)
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    outstanding_amount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    signed_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id",
            "business",
            "transaction_type",
            "amount",
            "amount_paid",
            "outstanding_amount",
            "signed_amount",
            "currency",
            "payment_status",
            "payment_method",
            "occurred_at",
            "description",
            "notes",
            "party",
            "party_name",
            "product",
            "product_name",
            "quantity",
            "unit_price",
            "source",
            "reference",
            "created_by",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "business",
            "currency",
            "created_by",
            "is_active",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            # Derived from quantity x unit_price when the client sends those instead.
            "amount": {"required": False, "allow_null": True},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # On a list request `instance` is a queryset, so only a single record
        # can tell us which business to scope the related fields to.
        instance = self.instance if isinstance(self.instance, Transaction) else None
        business = instance.business if instance else self.context.get("business")

        if business is None:
            return

        # Limiting the querysets means a party or product from another business
        # is simply not selectable, rather than relying on a later check.
        self.fields["party"].queryset = Party.objects.filter(
            business=business, is_active=True
        )
        self.fields["product"].queryset = Product.objects.filter(
            business=business, is_active=True
        )

    def validate_occurred_at(self, value):
        if value > timezone.now():
            raise serializers.ValidationError("A transaction cannot be dated in the future.")
        return value

    def validate_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Amount must be greater than zero.")
        return value

    def validate(self, attrs):
        instance = self.instance

        amount = attrs.get("amount", getattr(instance, "amount", None))
        quantity = attrs.get("quantity", getattr(instance, "quantity", None))
        unit_price = attrs.get("unit_price", getattr(instance, "unit_price", None))

        try:
            amount = resolve_amount(amount=amount, quantity=quantity, unit_price=unit_price)
        except LedgerRuleViolation as exc:
            raise serializers.ValidationError({"amount": str(exc)}) from exc

        # Downstream code should never have to re-derive the total.
        attrs["amount"] = amount

        status_given = "payment_status" in attrs
        paid_given = "amount_paid" in attrs

        if status_given or paid_given or instance is None:
            try:
                resolve_payment(
                    amount,
                    attrs.get("payment_status"),
                    attrs.get("amount_paid"),
                )
            except LedgerRuleViolation as exc:
                raise serializers.ValidationError({"amount_paid": str(exc)}) from exc

        return attrs
