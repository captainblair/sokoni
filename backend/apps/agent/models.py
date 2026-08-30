import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import BaseModel


class ConfirmationReason(models.TextChoices):
    LOW_CONFIDENCE = "low_confidence", _("Sokoni was unsure what it heard")
    UNUSUAL_AMOUNT = "unusual_amount", _("The amount is unlike this business")
    NEW_PARTY = "new_party", _("Nobody by that name has traded here before")


class PendingAction(BaseModel):
    """
    A write that has been understood but not yet committed.

    The parameters are stored exactly as they arrived and re-validated when the
    confirmation comes back, so answering "yes" commits the thing that was
    described and nothing else. A caller cannot smuggle different figures in
    behind a token it already holds.
    """

    business = models.ForeignKey(
        "businesses.Business", on_delete=models.CASCADE, related_name="pending_actions"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pending_actions",
    )

    token = models.CharField(_("token"), max_length=64, unique=True)
    tool = models.CharField(_("tool"), max_length=64)
    parameters = models.JSONField(_("parameters"), default=dict)

    question = models.CharField(_("question"), max_length=255)
    reason = models.CharField(
        _("reason"), max_length=32, choices=ConfirmationReason.choices
    )
    confidence = models.FloatField(_("confidence"), null=True, blank=True)

    expires_at = models.DateTimeField(_("expires at"))
    consumed_at = models.DateTimeField(_("consumed at"), null=True, blank=True)

    class Meta:
        verbose_name = _("pending action")
        verbose_name_plural = _("pending actions")
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["token"])]

    def __str__(self):
        return f"{self.tool} awaiting confirmation"

    @staticmethod
    def new_token() -> str:
        return secrets.token_urlsafe(32)[:64]

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_answerable(self) -> bool:
        return not self.is_consumed and not self.is_expired
