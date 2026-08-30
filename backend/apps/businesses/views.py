from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.businesses.models import Business
from apps.businesses.permissions import IsBusinessMember, IsBusinessOwner
from apps.businesses.serializers import (
    BusinessSerializer,
    MembershipCreateSerializer,
    MembershipRoleUpdateSerializer,
    MembershipSerializer,
)
from apps.businesses.services import (
    BusinessRuleViolation,
    archive_business,
    change_membership_role,
    create_business,
    remove_membership,
)

OWNER_ONLY_ACTIONS = {"update", "partial_update", "destroy", "manage_member"}


class BusinessViewSet(viewsets.ModelViewSet):
    """
    Businesses the requesting user belongs to.

    The queryset is scoped to the user's memberships, so an unknown or foreign
    business ID produces a 404 rather than revealing that the record exists.
    """

    serializer_class = BusinessSerializer
    permission_classes = [IsAuthenticated, IsBusinessMember]

    def get_queryset(self):
        return Business.objects.for_user(self.request.user)

    def get_permissions(self):
        if self.action in OWNER_ONLY_ACTIONS:
            return [IsAuthenticated(), IsBusinessOwner()]
        return super().get_permissions()

    def perform_create(self, serializer):
        serializer.instance = create_business(
            user=self.request.user, **serializer.validated_data
        )

    def destroy(self, request, *args, **kwargs):
        archive_business(self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, IsBusinessMember])
    def activate(self, request, pk=None):
        """Sets this business as the user's working context."""
        business = self.get_object()
        request.user.active_business = business
        request.user.save(update_fields=["active_business", "updated_at"])
        return Response(self.get_serializer(business).data)

    @action(
        detail=False,
        methods=["get"],
        permission_classes=[IsAuthenticated],
        url_path="active",
    )
    def active(self, request):
        business = request.user.active_business
        if business is None or not business.is_active:
            return Response(
                {"detail": "No active business selected."}, status=status.HTTP_404_NOT_FOUND
            )
        return Response(self.get_serializer(business).data)

    def require_owner(self, business):
        """
        Enforces ownership for a specific request.

        Needed where one action serves several methods, because DRF resolves
        permission classes per action rather than per HTTP method.
        """
        permission = IsBusinessOwner()
        if not permission.has_object_permission(self.request, self, business):
            self.permission_denied(self.request, message=permission.message)

    @action(detail=True, methods=["get", "post"], url_path="members")
    def members(self, request, pk=None):
        business = self.get_object()

        if request.method == "GET":
            memberships = business.memberships.select_related("user")
            return Response(MembershipSerializer(memberships, many=True).data)

        return self.add_member(request, business)

    def add_member(self, request, business):
        self.require_owner(business)

        serializer = MembershipCreateSerializer(
            data=request.data, context={"request": request, "business": business}
        )
        serializer.is_valid(raise_exception=True)
        membership = serializer.save()

        return Response(
            MembershipSerializer(membership).data, status=status.HTTP_201_CREATED
        )

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"members/(?P<membership_id>[^/.]+)",
    )
    def manage_member(self, request, pk=None, membership_id=None):
        business = self.get_object()
        membership = get_object_or_404(business.memberships, pk=membership_id)

        try:
            if request.method == "DELETE":
                remove_membership(membership)
                return Response(status=status.HTTP_204_NO_CONTENT)

            serializer = MembershipRoleUpdateSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            membership = change_membership_role(membership, serializer.validated_data["role"])
        except BusinessRuleViolation as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(MembershipSerializer(membership).data)
