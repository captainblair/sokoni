from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.core.constants import MONEY_DECIMAL_PLACES, MONEY_MAX_DIGITS
from apps.core.models import BusinessScopedModel


class Product(BusinessScopedModel):
    """
    Something the business buys or sells.

    Deliberately thin: a label, a unit and an optional usual price. Stock levels
    and reorder logic are a separate concern that the MVP does not need, and
    forcing traders to maintain inventory would defeat the point of speaking a
    sale in three seconds.
    """

    name = models.CharField(_("name"), max_length=120)
    unit = models.CharField(
        _("unit"),
        max_length=32,
        blank=True,
        help_text=_("How it is counted, e.g. crate, kg, piece, gunia."),
    )
    default_price = models.DecimalField(
        _("usual price"),
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text=_("Optional. Used as a suggestion, never as a fixed rate."),
    )
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("product")
        verbose_name_plural = _("products")
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "business",
                name="unique_product_name_per_business",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.unit})" if self.unit else self.name
