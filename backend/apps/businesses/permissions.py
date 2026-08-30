from rest_framework.permissions import BasePermission

from apps.businesses.models import MembershipRole


class IsBusinessMember(BasePermission):
    """Allows access only to users who belong to the business."""

    message = "You do not have access to this business."

    def has_object_permission(self, request, view, obj):
        business = getattr(obj, "business", obj)
        return business.is_member(request.user)


class IsBusinessOwner(BasePermission):
    """Restricts an action to owners of the business."""

    message = "Only a business owner can perform this action."

    def has_object_permission(self, request, view, obj):
        business = getattr(obj, "business", obj)
        return business.memberships.filter(
            user=request.user, role=MembershipRole.OWNER
        ).exists()
