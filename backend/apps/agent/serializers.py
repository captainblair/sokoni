from rest_framework import serializers


class ToolCallSerializer(serializers.Serializer):
    """
    A single instruction: which tool, with what, and how sure the caller is.

    `confidence` is what a speech pipeline will report in a later phase. It is
    optional here because a form or a script knows exactly what it means, and
    only a transcription has cause to be unsure.
    """

    tool = serializers.CharField()
    parameters = serializers.DictField(required=False, default=dict)
    confidence = serializers.FloatField(
        required=False, allow_null=True, min_value=0.0, max_value=1.0
    )
    transcript = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="The words this instruction came from, when there were any.",
    )
    confirmation_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs.get("confirmation_token") and attrs.get("parameters"):
            # The parked parameters are the ones that were described to the user,
            # so re-sending different ones could only mean confusion or mischief.
            raise serializers.ValidationError(
                {
                    "parameters": (
                        "A confirmation commits what was already described. Send the "
                        "token on its own."
                    )
                }
            )
        return attrs


class ConfirmationSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    question = serializers.CharField(read_only=True)
    reason = serializers.CharField(read_only=True)
    expires_at = serializers.DateTimeField(read_only=True)


class OutcomeSerializer(serializers.Serializer):
    status = serializers.CharField(read_only=True)
    tool = serializers.CharField(read_only=True)
    message = serializers.CharField(read_only=True)
    data = serializers.JSONField(read_only=True, allow_null=True)
    created = serializers.BooleanField(read_only=True)
    confirmation = ConfirmationSerializer(read_only=True, allow_null=True)
    options = serializers.ListField(child=serializers.CharField(), read_only=True)
