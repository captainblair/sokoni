from rest_framework import serializers

from apps.audit.models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    business = serializers.UUIDField(source="business_id", read_only=True)
    actor_email = serializers.EmailField(source="actor.email", read_only=True, allow_null=True)

    class Meta:
        model = AuditEvent
        fields = [
            "id",
            "business",
            "actor",
            "actor_email",
            "action",
            "object_type",
            "object_id",
            "summary",
            "before",
            "after",
            "source",
            "extra",
            "created_at",
        ]
        read_only_fields = fields
