from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.viewsets import BusinessScopedViewSet
from apps.ledger.models import Transaction
from apps.ledger.serializers import TransactionSerializer
from apps.ledger.services import (
    LedgerRuleViolation,
    archive_transaction,
    record_transaction,
    update_transaction,
)

FILTERABLE_FIELDS = {
    "type": "transaction_type",
    "status": "payment_status",
    "method": "payment_method",
    "source": "source",
    "party": "party_id",
    "product": "product_id",
}


class TransactionViewSet(BusinessScopedViewSet):
    """The business ledger: sales, other income, purchases and expenses."""

    queryset = Transaction.objects.select_related("party", "product")
    serializer_class = TransactionSerializer
    search_fields = ["description", "notes", "reference"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        for param, field in FILTERABLE_FIELDS.items():
            value = params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})

        if params.get("unsettled") == "true":
            queryset = queryset.unsettled()

        date_from = params.get("date_from")
        date_to = params.get("date_to")
        if date_from or date_to:
            queryset = queryset.in_period(date_from or None, date_to or None)

        return queryset

    def perform_create(self, serializer):
        try:
            serializer.instance = record_transaction(
                business=self.get_business(),
                created_by=self.request.user,
                **serializer.validated_data,
            )
        except LedgerRuleViolation as exc:
            raise ValidationError({"detail": str(exc)}) from exc

    def perform_update(self, serializer):
        try:
            serializer.instance = update_transaction(
                serializer.instance, **serializer.validated_data
            )
        except LedgerRuleViolation as exc:
            raise ValidationError({"detail": str(exc)}) from exc

    def destroy(self, request, *args, **kwargs):
        archive_transaction(self.get_object(), actor=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
