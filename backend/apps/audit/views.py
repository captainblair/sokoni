from drf_spectacular.utils import extend_schema
from rest_framework.mixins import ListModelMixin, RetrieveModelMixin
from rest_framework.viewsets import GenericViewSet

from apps.audit.models import AuditEvent
from apps.audit.serializers import AuditEventSerializer
from apps.businesses.models import Business
from apps.core.viewsets import BusinessScopedMixin


@extend_schema(tags=["audit"])
class AuditEventViewSet(
    BusinessScopedMixin, ListModelMixin, RetrieveModelMixin, GenericViewSet
):
    """
    The trail of money mutations for the selected business.

    Read-only: history is not something a client is allowed to edit, even by
    accident.
    """

    queryset = AuditEvent.objects.select_related("actor")
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        if getattr(self, "detail", False):
            return self.queryset.filter(
                business__in=Business.objects.for_user(self.request.user)
            )

        queryset = self.queryset.filter(business=self.get_business())
        params = self.request.query_params

        for param, field in (
            ("action", "action"),
            ("object_type", "object_type"),
            ("object_id", "object_id"),
            ("source", "source"),
        ):
            value = params.get(param)
            if value:
                queryset = queryset.filter(**{field: value})

        return queryset
