from rest_framework.routers import DefaultRouter

from apps.debts.views import DebtViewSet

router = DefaultRouter()
router.register("debts", DebtViewSet, basename="debt")

urlpatterns = router.urls
