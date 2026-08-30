"""
Turning spoken names into records.

A person speaking says "Mary", not a UUID, so the agent layer accepts names and
resolves them here. Three outcomes, each deliberate:

*One clear match* is used. *Several possible matches* is a question, not a guess —
paying the wrong Mary is worse than being asked which one. *No match at all* is a
new record, because a customer who has never been written down before is the
normal case for a business that has only ever used a notebook, and refusing to
proceed would just push the trader back to paper.
"""

from apps.agent.registry import Clarification
from apps.catalog.models import Product
from apps.parties.models import Party, PartyType


def _pick(queryset, name: str, kind: str):
    """Finds the one record meant by a name, or asks which was meant."""
    exact = queryset.filter(name__iexact=name).first()
    if exact is not None:
        return exact

    partial = list(queryset.filter(name__icontains=name)[:6])
    if len(partial) == 1:
        return partial[0]
    if len(partial) > 1:
        options = [record.name for record in partial]
        raise Clarification(
            f"Which {kind} did you mean: {_join(options)}?", options=options
        )
    return None


def _join(options: list[str]) -> str:
    if len(options) == 1:
        return options[0]
    return f"{', '.join(options[:-1])} or {options[-1]}"


def resolve_party(business, name: str, *, party_type: str = PartyType.CUSTOMER):
    """
    Finds or creates the party a name refers to.

    A party found as a customer who is now supplying goods becomes `both` rather
    than a second record, so the two balances can net against each other.
    """
    name = (name or "").strip()
    if not name:
        return None, False

    active = Party.objects.filter(business=business, is_active=True)
    party = _pick(active, name, "customer or supplier")

    if party is None:
        return (
            Party.objects.create(business=business, name=name, party_type=party_type),
            True,
        )

    if party_type not in (party.party_type, PartyType.BOTH) and party.party_type != PartyType.BOTH:
        party.party_type = PartyType.BOTH
        party.save(update_fields=["party_type", "updated_at"])

    return party, False


def resolve_product(business, name: str, *, unit: str = ""):
    name = (name or "").strip()
    if not name:
        return None, False

    active = Product.objects.filter(business=business, is_active=True)
    product = _pick(active, name, "product")

    if product is None:
        return (
            Product.objects.create(business=business, name=name, unit=unit),
            True,
        )
    return product, False
