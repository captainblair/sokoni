from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.core.viewsets import BusinessScopedViewSet
from apps.debts.models import Debt
from apps.debts.serializers import (
    DebtPaymentSerializer,
    DebtSerializer,
    WriteOffSerializer,
)
from apps.debts.services import (
    DebtRuleViolation,
    create_debt,
    record_payment,
    write_off_debt,
)

FILTERABLE_FIELDS = {
    "type": "debt_type",
    "status": "status",
    "party": "party_id",
}


class DebtViewSet(BusinessScopedViewSet):
    """Receivables and payables for the selected business."""

    queryset = Debt.objects.select_related("party").prefetch_related("payments")
    serializer_class = DebtSerializer
    search_fields = ["description", "notes", "party__name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        for param, field in FILTERABLE_FIELDS.items():
            value = params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})

        if params.get("outstanding") == "true":
            queryset = queryset.outstanding()

        if params.get("overdue") == "true":
            queryset = queryset.overdue()

        due_before = params.get("due_before")
        if due_before:
            queryset = queryset.filter(due_date__lte=due_before)

        return queryset

    def perform_create(self, serializer):
        try:
            serializer.instance = create_debt(
                business=self.get_business(),
                created_by=self.request.user,
                **serializer.validated_data,
            )
        except DebtRuleViolation as exc:
            raise ValidationError({"detail": str(exc)}) from exc

    def perform_update(self, serializer):
        debt = serializer.save()
        debt.status = debt.resolved_status()
        debt.save(update_fields=["status", "updated_at"])

    @action(detail=True, methods=["get", "post"], url_path="payments")
    def payments(self, request, pk=None):
        debt = self.get_object()

        if request.method == "GET":
            return Response(DebtPaymentSerializer(debt.payments.all(), many=True).data)

        serializer = DebtPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payment = record_payment(
                debt, created_by=request.user, **serializer.validated_data
            )
        except DebtRuleViolation as exc:
            raise ValidationError({"amount": str(exc)}) from exc

        return Response(
            DebtPaymentSerializer(payment).data, status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=["post"], url_path="write-off")
    def write_off(self, request, pk=None):
        debt = self.get_object()
        serializer = WriteOffSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            write_off_debt(debt, notes=serializer.validated_data.get("notes", ""))
        except DebtRuleViolation as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(self.get_serializer(debt).data)
