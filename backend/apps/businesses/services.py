from django.db import transaction

from apps.businesses.models import Business, Membership, MembershipRole


class BusinessRuleViolation(Exception):
    """Raised when an operation would leave a business in an invalid state."""


@transaction.atomic
def create_business(*, user, **fields) -> Business:
    """
    Creates a business, makes the creator its owner, and selects it when the
    user has no active business yet.
    """
    business = Business.objects.create(created_by=user, **fields)
    Membership.objects.create(business=business, user=user, role=MembershipRole.OWNER)

    if user.active_business_id is None:
        user.active_business = business
        user.save(update_fields=["active_business", "updated_at"])

    return business


@transaction.atomic
def archive_business(business: Business) -> Business:
    """
    Deactivates a business instead of deleting it.

    Financial history must remain recoverable and auditable, so rows are never
    destroyed on the owner's behalf.
    """
    business.is_active = False
    business.save(update_fields=["is_active", "updated_at"])

    business.users_with_active.update(active_business=None)
    return business


def remove_membership(membership: Membership) -> None:
    """Removes a member, refusing to strip a business of its last owner."""
    business = membership.business

    if membership.role == MembershipRole.OWNER and business.owner_count <= 1:
        raise BusinessRuleViolation("A business must always have at least one owner.")

    user = membership.user
    membership.delete()

    if user.active_business_id == business.id:
        user.active_business = None
        user.save(update_fields=["active_business", "updated_at"])


def change_membership_role(membership: Membership, role: str) -> Membership:
    """Changes a member's role, refusing to demote the final owner."""
    if (
        membership.role == MembershipRole.OWNER
        and role != MembershipRole.OWNER
        and membership.business.owner_count <= 1
    ):
        raise BusinessRuleViolation("A business must always have at least one owner.")

    membership.role = role
    membership.save(update_fields=["role", "updated_at"])
    return membership
