from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.agent import confirmation, execution
from apps.agent.registry import ToolContext, ToolError, UnknownTool, all_tools, get_tool
from apps.agent.serializers import OutcomeSerializer, ToolCallSerializer
from apps.core.throttles import AgentRateThrottle
from apps.core.viewsets import BusinessScopedMixin


class ToolRegistryView(APIView):
    """
    The contract an AI is given.

    Published as data rather than written into a prompt, so a model's idea of what
    it may do cannot drift from what the backend will actually allow.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["agent"])
    def get(self, request):
        return Response({"tools": [tool.schema() for tool in all_tools()]})


class ExecuteToolView(BusinessScopedMixin, APIView):
    """
    Runs one tool from the registry.

    Everything an AI will ever do to the books goes through this one door, which
    is what makes the rule enforceable rather than aspirational: there is no
    second entrance, and no way to reach the database except through a tool.
    """

    throttle_classes = [AgentRateThrottle]

    @extend_schema(
        tags=["agent"],
        request=ToolCallSerializer,
        responses={200: OutcomeSerializer, 201: OutcomeSerializer, 400: OutcomeSerializer},
    )
    def post(self, request):
        call = ToolCallSerializer(data=request.data)
        call.is_valid(raise_exception=True)
        instruction = call.validated_data

        try:
            tool = get_tool(instruction["tool"])
        except UnknownTool as exc:
            raise ValidationError({"tool": str(exc)}) from exc

        business = self.get_business()
        context = ToolContext(business=business, user=request.user)

        token = instruction.get("confirmation_token")
        if token:
            try:
                pending = confirmation.consume(
                    token, user=request.user, business=business
                )
            except confirmation.ConfirmationInvalid as exc:
                raise ValidationError({"confirmation_token": str(exc)}) from exc

            if pending.tool != tool.name:
                raise ValidationError(
                    {"confirmation_token": "That confirmation was for another action."}
                )

            raw = pending.parameters
            confidence = pending.confidence
            confirmed = True
        else:
            raw = instruction.get("parameters") or {}
            confidence = instruction.get("confidence")
            confirmed = False

        parameters = tool.parameters(data=raw)
        parameters.is_valid(raise_exception=True)

        try:
            outcome = execution.execute(
                tool,
                context,
                parameters.validated_data,
                raw_parameters=raw,
                confidence=confidence,
                confirmed=confirmed,
            )
        except ToolError as exc:
            # A refusal, not a crash: the instruction was understood and cannot be
            # carried out, and the reason is something a person can be told.
            return Response(
                {"status": "rejected", "tool": tool.name, "message": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        code = (
            status.HTTP_201_CREATED
            if outcome.created and outcome.status == execution.EXECUTED
            else status.HTTP_200_OK
        )
        return Response(OutcomeSerializer(outcome).data, status=code)
