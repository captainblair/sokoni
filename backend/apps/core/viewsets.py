from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.businesses.models import Business


class BusinessScopedViewSet(viewsets.ModelViewSet):
    """
    Base viewset for resources owned by a single business.

    The business is resolved from an explicit `business` value when the client
    sends one, otherwise from the user's active business — voice commands in
    particular arrive without naming a business. Either way the choice is
    validated against the user's memberships, so this is the only place tenant
    scoping has to be implemented correctly.
    """

    permission_classes = [IsAuthenticated]
    search_fields: list[str] = []

    def get_business(self) -> Business:
        if hasattr(self, "_resolved_business"):
            return self._resolved_business

        available = Business.objects.for_user(self.request.user)
        requested = self.request.data.get("business") or self.request.query_params.get(
            "business"
        )

        if requested:
            try:
                business = available.filter(pk=requested).first()
            except (DjangoValidationError, ValueError) as exc:
                raise ValidationError({"business": "Not a valid business id."}) from exc

            if business is None:
                # 404 rather than 403: never confirm a foreign business exists.
                raise NotFound("Business not found.")
        else:
            business = self.request.user.active_business
            if business is None or not available.filter(pk=business.pk).exists():
                raise ValidationError(
                    {
                        "business": (
                            "No active business selected. Activate a business or "
                            "send a business id with the request."
                        )
                    }
                )

        self._resolved_business = business
        return business

    def get_queryset(self):
        if getattr(self, "detail", False):
            # A record is addressed by its own ID, so it only has to belong to
            # one of the user's businesses — not necessarily the active one.
            queryset = self.queryset.filter(
                business__in=Business.objects.for_user(self.request.user)
            )
            return queryset

        queryset = self.queryset.filter(business=self.get_business())

        if self.request.query_params.get("include_archived") != "true":
            queryset = queryset.filter(is_active=True)

        return self.filter_queryset_by_search(queryset)

    def filter_queryset_by_search(self, queryset):
        term = self.request.query_params.get("search")
        if not term or not self.search_fields:
            return queryset

        from django.db.models import Q

        query = Q()
        for field in self.search_fields:
            query |= Q(**{f"{field}__icontains": term})
        return queryset.filter(query)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        # Serializers need the business to enforce per-business uniqueness.
        if self.request and self.request.user.is_authenticated:
            try:
                context["business"] = self.get_business()
            except (ValidationError, NotFound):
                context["business"] = None
        return context

    def perform_create(self, serializer):
        serializer.save(business=self.get_business())

    def destroy(self, request, *args, **kwargs):
        self.get_object().archive()
        return Response(status=status.HTTP_204_NO_CONTENT)
