from rest_framework.routers import DefaultRouter

from apps.parties.views import PartyViewSet

router = DefaultRouter()
router.register("parties", PartyViewSet, basename="party")

urlpatterns = router.urls
