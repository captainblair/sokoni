from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.viewsets import BusinessScopedMixin
from apps.finance import selectors
from apps.finance.brief import daily_brief
from apps.finance.periods import UnknownPeriod, resolve_period
from apps.finance.serializers import (
    CashPositionSerializer,
    DailyBriefSerializer,
    FloatRiskSerializer,
    SummarySerializer,
)

MAX_HORIZON_DAYS = 365


@extend_schema(tags=["finance"])
class FinanceView(BusinessScopedMixin, APIView):
    """Base for the read-only finance reports."""

    serializer_class = None

    def calculate(self, business):
        raise NotImplementedError

    def get(self, request):
        data = self.calculate(self.get_business())
        return Response(self.serializer_class(data).data)


class CashPositionView(FinanceView):
    """What is in hand, and what is still owed in each direction."""

    serializer_class = CashPositionSerializer

    def calculate(self, business):
        return selectors.cash_position(business)


class SummaryView(FinanceView):
    """Revenue, costs and cash movement over a period."""

    serializer_class = SummarySerializer

    def calculate(self, business):
        try:
            period = resolve_period(self.request.query_params)
        except UnknownPeriod as exc:
            raise ValidationError({"period": str(exc)}) from exc

        return selectors.summary(business, period)


class FloatRiskView(FinanceView):
    """Whether the business can meet what falls due soon."""

    serializer_class = FloatRiskSerializer

    def calculate(self, business):
        return selectors.float_risk(business, horizon_days=self.horizon_days())

    def horizon_days(self) -> int:
        raw = self.request.query_params.get("days")
        if raw is None:
            return selectors.DEFAULT_HORIZON_DAYS

        try:
            days = int(raw)
        except ValueError as exc:
            raise ValidationError({"days": "Must be a whole number of days."}) from exc

        if not 1 <= days <= MAX_HORIZON_DAYS:
            raise ValidationError(
                {"days": f"Must be between 1 and {MAX_HORIZON_DAYS}."}
            )
        return days


class DailyBriefView(FinanceView):
    """The whole picture, in sentences that can be read aloud."""

    serializer_class = DailyBriefSerializer

    def calculate(self, business):
        return daily_brief(business)
