import uuid

from django.db import models


class UUIDPrimaryKeyModel(models.Model):
    """
    Gives a model a non-guessable identifier.

    Financial records are addressed by ID in the API, so sequential integers
    would leak both record counts and the existence of other tenants' data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Tracks when a row was created and last changed."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(UUIDPrimaryKeyModel, TimeStampedModel):
    """Default base for Sokoni domain models."""

    class Meta:
        abstract = True
