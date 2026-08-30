from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.constants import (
    DEFAULT_CURRENCY,
    MONEY_DECIMAL_PLACES,
    MONEY_MAX_DIGITS,
)
from apps.core.models import BaseModel, BusinessScopedModel
from apps.ledger.models import PaymentMethod, TransactionSource

ZERO = Decimal("0.00")


class DebtType(models.TextChoices):
    RECEIVABLE = "receivable", _("Owed to the business")
    PAYABLE = "payable", _("Owed by the business")


class DebtStatus(models.TextChoices):
    OPEN = "open", _("Nothing paid yet")
    PARTIAL = "partial", _("Partly paid")
    SETTLED = "settled", _("Fully paid")
    WRITTEN_OFF = "written_off", _("Written off")


class AgingBucket(models.TextChoices):
    CURRENT = "current", _("Not yet due")
    DUE_1_7 = "1-7", _("1 to 7 days overdue")
    DUE_8_30 = "8-30", _("8 to 30 days overdue")
    DUE_31_60 = "31-60", _("31 to 60 days overdue")
    DUE_60_PLUS = "60+", _("More than 60 days overdue")


class DebtQuerySet(models.QuerySet):
    def outstanding(self):
        """Debts with money still to move."""
        return self.filter(status__in=[DebtStatus.OPEN, DebtStatus.PARTIAL])

    def receivables(self):
        return self.filter(debt_type=DebtType.RECEIVABLE)

    def payables(self):
        return self.filter(debt_type=DebtType.PAYABLE)

    def overdue(self, as_of=None):
        as_of = as_of or timezone.localdate()
        return self.outstanding().filter(due_date__isnull=False, due_date__lt=as_of)


class Debt(BusinessScopedModel):
    """
    Money owed in one direction or the other.

    A debt is not an expense and not income: it is an obligation. Recording it
    as a transaction would either overstate cash or lose track of who owes what,
    which is exactly the failure mode a paper notebook has.
    """

    debt_type = models.CharField(_("type"), max_length=16, choices=DebtType.choices)
    party = models.ForeignKey(
        "parties.Party",
        on_delete=models.PROTECT,
        related_name="debts",
        help_text=_("A debt always belongs to someone."),
    )

    original_amount = models.DecimalField(
        _("original amount"),
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    amount_paid = models.DecimalField(
        _("amount paid"),
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=ZERO,
        validators=[MinValueValidator(ZERO)],
    )
    currency = models.CharField(_("currency"), max_length=3, default=DEFAULT_CURRENCY)

    status = models.CharField(
        _("status"), max_length=16, choices=DebtStatus.choices, default=DebtStatus.OPEN
    )
    due_date = models.DateField(_("due date"), null=True, blank=True)

    description = models.CharField(_("description"), max_length=255, blank=True)
    notes = models.TextField(_("notes"), blank=True)

    source_transaction = models.OneToOneField(
        "ledger.Transaction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debt",
        help_text=_("The credit sale or purchase this debt came from, if any."),
    )
    source = models.CharField(
        _("source"),
        max_length=16,
        choices=TransactionSource.choices,
        default=TransactionSource.MANUAL,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debts_created",
    )

    objects = DebtQuerySet.as_manager()

    class Meta:
        verbose_name = _("debt")
        verbose_name_plural = _("debts")
        ordering = ["due_date", "-created_at"]
        indexes = [
            models.Index(fields=["business", "debt_type", "status"]),
            models.Index(fields=["business", "due_date"]),
        ]

    def __str__(self):
        direction = "owes us" if self.debt_type == DebtType.RECEIVABLE else "we owe"
        return f"{self.party} {direction} {self.currency} {self.balance}"

    @property
    def balance(self) -> Decimal:
        """What is still owed."""
        if self.status == DebtStatus.WRITTEN_OFF:
            return ZERO
        return self.original_amount - self.amount_paid

    @property
    def is_settled(self) -> bool:
        return self.status in {DebtStatus.SETTLED, DebtStatus.WRITTEN_OFF}

    @property
    def days_overdue(self) -> int:
        if self.due_date is None or self.is_settled:
            return 0
        overdue = (timezone.localdate() - self.due_date).days
        return max(overdue, 0)

    @property
    def is_overdue(self) -> bool:
        return self.days_overdue > 0

    @property
    def aging_bucket(self) -> str:
        days = self.days_overdue
        if days == 0:
            return AgingBucket.CURRENT
        if days <= 7:
            return AgingBucket.DUE_1_7
        if days <= 30:
            return AgingBucket.DUE_8_30
        if days <= 60:
            return AgingBucket.DUE_31_60
        return AgingBucket.DUE_60_PLUS

    def resolved_status(self) -> str:
        """The status implied by the amounts, unless the debt was written off."""
        if self.status == DebtStatus.WRITTEN_OFF:
            return DebtStatus.WRITTEN_OFF
        if self.amount_paid >= self.original_amount:
            return DebtStatus.SETTLED
        if self.amount_paid > ZERO:
            return DebtStatus.PARTIAL
        return DebtStatus.OPEN


class DebtPayment(BaseModel):
    """
    One instalment against a debt.

    Kept as its own record so a trader can see that Mary paid 500 on Monday and
    300 on Thursday, rather than only a shrinking balance.
    """

    debt = models.ForeignKey(Debt, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(
        _("amount"),
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    paid_at = models.DateTimeField(_("paid at"), default=timezone.now)
    payment_method = models.CharField(
        _("payment method"),
        max_length=16,
        choices=PaymentMethod.choices,
        default=PaymentMethod.CASH,
    )
    notes = models.TextField(_("notes"), blank=True)
    source = models.CharField(
        _("source"),
        max_length=16,
        choices=TransactionSource.choices,
        default=TransactionSource.MANUAL,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="debt_payments_recorded",
    )

    class Meta:
        verbose_name = _("debt payment")
        verbose_name_plural = _("debt payments")
        ordering = ["-paid_at", "-created_at"]

    def __str__(self):
        return f"{self.amount} against {self.debt_id}"
