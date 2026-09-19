from rest_framework import serializers


class HealthCheckSerializer(serializers.Serializer):
    status = serializers.CharField()
    service = serializers.CharField()
    database = serializers.CharField()
    database_error = serializers.CharField(required=False)


class ToolParameterSerializer(serializers.Serializer):
    name = serializers.CharField()
    type = serializers.CharField()
    required = serializers.BooleanField()
    description = serializers.CharField()
    choices = serializers.ListField(child=serializers.CharField(), required=False)


class ToolSchemaSerializer(serializers.Serializer):
    name = serializers.CharField()
    description = serializers.CharField()
    mutating = serializers.BooleanField()
    parameters = ToolParameterSerializer(many=True)


class ToolRegistrySerializer(serializers.Serializer):
    tools = ToolSchemaSerializer(many=True)


class MessageSerializer(serializers.Serializer):
    detail = serializers.CharField()
