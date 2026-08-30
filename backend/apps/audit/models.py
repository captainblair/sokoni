from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import UUIDPrimaryKeyModel


class AuditAction(models.TextChoices):
    CREATED = "created", _("Created")
    UPDATED = "updated", _("Updated")
    PAID = "paid", _("Payment recorded")
    WRITTEN_OFF = "written_off", _("Written off")
    ARCHIVED = "archived", _("Archived")


class AuditObjectType(models.TextChoices):
    TRANSACTION = "transaction", _("Transaction")
    DEBT = "debt", _("Debt")
    DEBT_PAYMENT = "debt_payment", _("Debt payment")


class AuditIntegrityError(Exception):
    """Raised when someone tries to rewrite or erase history."""


class AuditEvent(UUIDPrimaryKeyModel):
    """
    One financial mutation, written once and never again.

    The books can be corrected — a misheard 24,000 becomes 2,400 — but the fact
    that the correction happened stays. Without that trail, a voice interface
    that is allowed to change money would be unauditable, and a paper notebook
    would be the more honest tool.
    """

    created_at = models.DateTimeField(_("recorded at"), auto_now_add=True)

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )

    action = models.CharField(_("action"), max_length=16, choices=AuditAction.choices)
    object_type = models.CharField(
        _("object type"), max_length=16, choices=AuditObjectType.choices
    )
    object_id = models.UUIDField(_("object id"))

    summary = models.CharField(_("summary"), max_length=255)
    before = models.JSONField(_("before"), null=True, blank=True)
    after = models.JSONField(_("after"), null=True, blank=True)
    source = models.CharField(_("source"), max_length=16, blank=True)
    extra = models.JSONField(_("extra"), default=dict, blank=True)

    class Meta:
        verbose_name = _("audit event")
        verbose_name_plural = _("audit events")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["business", "-created_at"]),
            models.Index(fields=["business", "object_type", "object_id"]),
        ]

    def __str__(self):
        return self.summary

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise AuditIntegrityError("Audit events cannot be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise AuditIntegrityError("Audit events cannot be deleted.")
