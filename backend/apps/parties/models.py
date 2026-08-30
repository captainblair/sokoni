from django.db import models
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import phone_validator
from apps.core.models import BusinessScopedModel


class PartyType(models.TextChoices):
    CUSTOMER = "customer", _("Customer")
    SUPPLIER = "supplier", _("Supplier")
    BOTH = "both", _("Customer and supplier")


class Party(BusinessScopedModel):
    """
    A person or organisation the business trades with.

    Debts in a later phase attach to a party, which is why a customer who also
    supplies goods is one record rather than two — their balances have to net
    against each other.
    """

    name = models.CharField(_("name"), max_length=120)
    party_type = models.CharField(
        _("type"), max_length=16, choices=PartyType.choices, default=PartyType.CUSTOMER
    )
    phone_number = models.CharField(
        _("phone number"), max_length=20, blank=True, validators=[phone_validator]
    )
    notes = models.TextField(_("notes"), blank=True)

    class Meta:
        verbose_name = _("party")
        verbose_name_plural = _("parties")
        ordering = ["name"]
        constraints = [
            # Names are matched case-insensitively so that a spoken "Jane" does
            # not create a second record alongside an existing "jane".
            models.UniqueConstraint(
                Lower("name"),
                "business",
                name="unique_party_name_per_business",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def is_customer(self):
        return self.party_type in {PartyType.CUSTOMER, PartyType.BOTH}

    @property
    def is_supplier(self):
        return self.party_type in {PartyType.SUPPLIER, PartyType.BOTH}
