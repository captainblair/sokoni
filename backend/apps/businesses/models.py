from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import phone_validator
from apps.core.models import BaseModel


class BusinessType(models.TextChoices):
    RETAIL = "retail", _("Retail shop")
    MARKET_VENDOR = "market_vendor", _("Market vendor")
    FOOD = "food", _("Food and beverage")
    SERVICES = "services", _("Services")
    TRANSPORT = "transport", _("Transport")
    FREELANCE = "freelance", _("Freelance")
    AGRICULTURE = "agriculture", _("Agriculture")
    OTHER = "other", _("Other")


class BusinessQuerySet(models.QuerySet):
    def for_user(self, user):
        """Every business the user belongs to. The only safe entry point for API queries."""
        if not user or not user.is_authenticated:
            return self.none()
        return self.filter(memberships__user=user, is_active=True).distinct()


class Business(BaseModel):
    """
    A trading entity owned by one or more users.

    All financial records added in later phases hang off this model, which makes
    it the tenancy boundary for the whole system.
    """

    name = models.CharField(_("business name"), max_length=120)
    business_type = models.CharField(
        _("business type"),
        max_length=32,
        choices=BusinessType.choices,
        default=BusinessType.OTHER,
    )
    currency = models.CharField(_("currency"), max_length=3, default="KES")
    location = models.CharField(_("location"), max_length=120, blank=True)
    phone_number = models.CharField(
        _("phone number"), max_length=20, blank=True, validators=[phone_validator]
    )
    description = models.TextField(_("description"), blank=True)

    # Archived rather than deleted, so financial history is never silently lost.
    is_active = models.BooleanField(_("active"), default=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="businesses_created",
    )

    objects = BusinessQuerySet.as_manager()

    class Meta:
        verbose_name = _("business")
        verbose_name_plural = _("businesses")
        ordering = ["name"]

    def __str__(self):
        return self.name

    def membership_for(self, user):
        return self.memberships.filter(user=user).first()

    def is_member(self, user):
        return self.memberships.filter(user=user).exists()

    def is_owner(self, user):
        return self.memberships.filter(user=user, role=MembershipRole.OWNER).exists()

    @property
    def owner_count(self):
        return self.memberships.filter(role=MembershipRole.OWNER).count()


class MembershipRole(models.TextChoices):
    OWNER = "owner", _("Owner")
    MEMBER = "member", _("Member")


class Membership(BaseModel):
    """Links a user to a business and defines what they may do there."""

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(
        _("role"), max_length=16, choices=MembershipRole.choices, default=MembershipRole.MEMBER
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="memberships_invited",
    )

    class Meta:
        verbose_name = _("membership")
        verbose_name_plural = _("memberships")
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["business", "user"], name="unique_business_membership")
        ]

    def __str__(self):
        return f"{self.user} @ {self.business} ({self.role})"

    @property
    def is_owner(self):
        return self.role == MembershipRole.OWNER
