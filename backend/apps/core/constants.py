"""Shared numeric conventions for monetary values."""

# Large enough for any realistic informal-business amount without inviting
# float-style rounding surprises. Money is always Decimal, never float.
MONEY_MAX_DIGITS = 12
MONEY_DECIMAL_PLACES = 2

DEFAULT_CURRENCY = "KES"
