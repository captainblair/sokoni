"""
The fixed set of operations an AI may perform.

This registry is the boundary the whole AI design rests on. The model never sees
a database, never composes a query and never invents an operation: it picks a
name from this list and supplies parameters, which are validated like any other
API input before a domain service is allowed to write anything.

Nothing here knows that an LLM exists. A tool is callable by a test, a script or
a form submission in exactly the same way, which is what makes the layer
verifiable on its own — and why this phase carries no AI at all.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Callable

from rest_framework import serializers


class UnknownTool(Exception):
    """Raised when a caller names a tool that does not exist."""


class ImproperlyRegistered(Exception):
    """Raised when two tools claim the same name."""


class ToolError(Exception):
    """Raised when a tool cannot complete for a business reason."""


class Clarification(Exception):
    """
    Raised when an instruction is understandable but not specific enough.

    Distinct from a confirmation: the answer is not yes or no, it is *which one*,
    and the caller has to come back with a better parameter rather than a token.
    """

    def __init__(self, question: str, options: list[str] | None = None):
        super().__init__(question)
        self.question = question
        self.options = options or []


@dataclass(frozen=True)
class ToolContext:
    """Who is asking, and on whose books."""

    business: object
    user: object


@dataclass(frozen=True)
class ToolResult:
    """What a tool did, and how to say so out loud."""

    message: str
    data: dict | None = None
    created: bool = False


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: type[serializers.Serializer]
    handler: Callable[[ToolContext, dict], ToolResult]
    #: Whether this tool writes. Reads are never confirmed; writes may be.
    mutating: bool = False
    #: Resolves spoken names into records before anything is decided or written.
    #: Kept apart from the handler so that whether to ask the user can be judged
    #: against real records, and abandoned without having written anything.
    prepare: Callable[[ToolContext, dict], dict] | None = None
    #: Renders the action as a noun phrase — "a sale of KES 2,400 to Mary" — used
    #: both to ask "did you mean ...?" and to report what was recorded.
    phrase: Callable[[ToolContext, dict], str] | None = None
    #: Parameter holding the money at stake, for the misheard-amount check.
    amount_field: str = "amount"

    def schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "mutating": self.mutating,
            "parameters": _describe(self.parameters()),
        }

    def amount(self, params: dict) -> Decimal | None:
        value = params.get(self.amount_field)
        return Decimal(value) if value is not None else None


_FIELD_TYPES = [
    (serializers.BooleanField, "boolean"),
    (serializers.DecimalField, "decimal"),
    (serializers.IntegerField, "integer"),
    (serializers.FloatField, "number"),
    (serializers.DateTimeField, "datetime"),
    (serializers.DateField, "date"),
    (serializers.ChoiceField, "string"),
    (serializers.CharField, "string"),
]


def _describe(serializer: serializers.Serializer) -> list[dict]:
    """
    Turns a serializer into a parameter list.

    Written by hand rather than pulled from OpenAPI because this description is
    what a language model will be handed in a later phase, and it needs the
    vocabulary — the choices, the help text — more than it needs formal types.
    """
    described = []
    for name, instance in serializer.fields.items():
        entry = {
            "name": name,
            "type": next(
                (label for cls, label in _FIELD_TYPES if isinstance(instance, cls)),
                "string",
            ),
            "required": instance.required,
            "description": str(instance.help_text or ""),
        }
        choices = getattr(instance, "choices", None)
        if choices:
            entry["choices"] = list(choices)
        described.append(entry)
    return described


_REGISTRY: dict[str, Tool] = {}


def register(**kwargs) -> Callable:
    """Declares a tool. The decorated function becomes its handler."""

    def wrap(handler):
        tool = Tool(handler=handler, **kwargs)
        if tool.name in _REGISTRY:
            raise ImproperlyRegistered(f"Tool '{tool.name}' is already registered.")
        _REGISTRY[tool.name] = tool
        return handler

    return wrap


def get_tool(name: str) -> Tool:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise UnknownTool(f"There is no tool called '{name}'.") from exc


def all_tools() -> list[Tool]:
    return sorted(_REGISTRY.values(), key=lambda tool: tool.name)
