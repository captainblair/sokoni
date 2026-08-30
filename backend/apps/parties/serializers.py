from rest_framework import serializers

from apps.parties.models import Party


class PartySerializer(serializers.ModelSerializer):
    business = serializers.UUIDField(source="business_id", read_only=True)

    class Meta:
        model = Party
        fields = [
            "id",
            "business",
            "name",
            "party_type",
            "phone_number",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "business", "is_active", "created_at", "updated_at"]

    def validate_name(self, value):
        name = value.strip()
        if not name:
            raise serializers.ValidationError("Name cannot be blank.")

        # On update the record's own business wins; the active business is only
        # relevant when creating.
        business = self.instance.business if self.instance else self.context.get("business")
        if business is None:
            return name

        duplicates = Party.objects.filter(business=business, name__iexact=name)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise serializers.ValidationError(
                f"'{name}' already exists for this business."
            )

        return name
