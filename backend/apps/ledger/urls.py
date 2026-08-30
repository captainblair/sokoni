from rest_framework.routers import DefaultRouter

from apps.ledger.views import TransactionViewSet

router = DefaultRouter()
router.register("transactions", TransactionViewSet, basename="transaction")

urlpatterns = router.urls
