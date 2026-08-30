import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.managers import UserManager

phone_validator = RegexValidator(
    regex=r"^\+?[0-9]{7,15}$",
    message=_("Enter a valid phone number, e.g. +254712345678."),
)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Sokoni account holder.

    Identified by email rather than username, and keyed by UUID so that
    account identifiers are never guessable from a sequential API path.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_("email address"), unique=True)
    full_name = models.CharField(_("full name"), max_length=150, blank=True)
    phone_number = models.CharField(
        _("phone number"),
        max_length=20,
        blank=True,
        validators=[phone_validator],
        help_text=_("Optional. Used for future M-Pesa and reminder features."),
    )

    is_active = models.BooleanField(_("active"), default=True)
    is_staff = models.BooleanField(_("staff status"), default=False)

    # The business a request applies to when the client does not name one.
    # Voice commands in particular arrive without an explicit business.
    active_business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users_with_active",
    )

    date_joined = models.DateTimeField(_("date joined"), default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["-date_joined"]

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = self.email.lower().strip()
        return super().save(*args, **kwargs)

    def get_full_name(self):
        return self.full_name or self.email

    def get_short_name(self):
        return self.full_name.split(" ")[0] if self.full_name else self.email
