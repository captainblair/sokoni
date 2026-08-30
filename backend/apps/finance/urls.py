from django.urls import path

from apps.finance.views import (
    CashPositionView,
    DailyBriefView,
    FloatRiskView,
    SummaryView,
)

urlpatterns = [
    path("finance/cash-position/", CashPositionView.as_view(), name="cash-position"),
    path("finance/summary/", SummaryView.as_view(), name="finance-summary"),
    path("finance/float-risk/", FloatRiskView.as_view(), name="float-risk"),
    path("finance/daily-brief/", DailyBriefView.as_view(), name="daily-brief"),
]
