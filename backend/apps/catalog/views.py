from apps.catalog.models import Product
from apps.catalog.serializers import ProductSerializer
from apps.core.viewsets import BusinessScopedViewSet


class ProductViewSet(BusinessScopedViewSet):
    """Products belonging to the selected business."""

    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    search_fields = ["name", "unit"]
