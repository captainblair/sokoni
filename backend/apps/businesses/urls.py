from rest_framework.routers import DefaultRouter

from apps.businesses.views import BusinessViewSet

router = DefaultRouter()
router.register("businesses", BusinessViewSet, basename="business")

urlpatterns = router.urls
