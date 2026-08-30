"""
The one path from an instruction to a change in the books.

The order of steps is the whole point, and it is the order the architecture
promised: validate the shape, resolve the names, decide whether to ask, and only
then let a domain service write. Nothing skips ahead.

Preparation can create records — a customer nobody had written down before — so
it runs inside a savepoint. If the answer turns out to be "ask the user first",
that savepoint is rolled back and the request leaves no trace behind except the
question itself.
"""

from dataclasses import dataclass, field

from django.db import transaction as db_transaction

from apps.agent import confirmation
from apps.agent.registry import Clarification, Tool, ToolContext, ToolError, ToolResult

EXECUTED = "executed"
CONFIRMATION_REQUIRED = "confirmation_required"
CLARIFICATION_REQUIRED = "clarification_required"


@dataclass
class Outcome:
    """What came of an instruction, in a shape the caller can act on."""

    status: str
    tool: str
    message: str
    data: object = None
    created: bool = False
    confirmation: dict | None = None
    options: list[str] = field(default_factory=list)


@db_transaction.atomic
def execute(
    tool: Tool,
    context: ToolContext,
    validated: dict,
    *,
    raw_parameters: dict | None = None,
    confidence: float | None = None,
    confirmed: bool = False,
) -> Outcome:
    """
    Runs one tool.

    `confirmed` is set only when a token has been redeemed. The checks are skipped
    in that case because they have already been answered — asking the same
    question again on the way back would make confirmation impossible to complete.
    """
    savepoint = db_transaction.savepoint()

    try:
        prepared = tool.prepare(context, validated) if tool.prepare else dict(validated)
    except Clarification as exc:
        db_transaction.savepoint_rollback(savepoint)
        return Outcome(
            status=CLARIFICATION_REQUIRED,
            tool=tool.name,
            message=exc.question,
            options=exc.options,
        )
    except ToolError:
        db_transaction.savepoint_rollback(savepoint)
        raise

    if not confirmed:
        verdict = confirmation.review(tool, context, prepared, confidence)
        if verdict.required:
            # Undo anything preparation created: a question must not leave
            # half-finished records lying around if it is never answered.
            db_transaction.savepoint_rollback(savepoint)
            pending = confirmation.hold(
                tool, context, raw_parameters or {}, verdict, confidence
            )
            return Outcome(
                status=CONFIRMATION_REQUIRED,
                tool=tool.name,
                message=verdict.question,
                confirmation={
                    "token": pending.token,
                    "question": pending.question,
                    "reason": pending.reason,
                    "expires_at": pending.expires_at,
                },
            )

    try:
        result: ToolResult = tool.handler(context, prepared)
    except Clarification as exc:
        db_transaction.savepoint_rollback(savepoint)
        return Outcome(
            status=CLARIFICATION_REQUIRED,
            tool=tool.name,
            message=exc.question,
            options=exc.options,
        )
    except ToolError:
        db_transaction.savepoint_rollback(savepoint)
        raise

    db_transaction.savepoint_commit(savepoint)
    return Outcome(
        status=EXECUTED,
        tool=tool.name,
        message=result.message,
        data=result.data,
        created=result.created,
    )
