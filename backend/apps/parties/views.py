from apps.core.viewsets import BusinessScopedViewSet
from apps.parties.models import Party, PartyType
from apps.parties.serializers import PartySerializer


class PartyViewSet(BusinessScopedViewSet):
    """Customers and suppliers belonging to the selected business."""

    queryset = Party.objects.all()
    serializer_class = PartySerializer
    search_fields = ["name", "phone_number"]

    def get_queryset(self):
        queryset = super().get_queryset()

        party_type = self.request.query_params.get("type")
        if party_type == PartyType.CUSTOMER:
            queryset = queryset.filter(
                party_type__in=[PartyType.CUSTOMER, PartyType.BOTH]
            )
        elif party_type == PartyType.SUPPLIER:
            queryset = queryset.filter(
                party_type__in=[PartyType.SUPPLIER, PartyType.BOTH]
            )

        return queryset
