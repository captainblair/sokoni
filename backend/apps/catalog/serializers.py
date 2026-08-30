from rest_framework import serializers

from apps.catalog.models import Product


class ProductSerializer(serializers.ModelSerializer):
    business = serializers.UUIDField(source="business_id", read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "business",
            "name",
            "unit",
            "default_price",
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

        business = self.instance.business if self.instance else self.context.get("business")
        if business is None:
            return name

        duplicates = Product.objects.filter(business=business, name__iexact=name)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise serializers.ValidationError(
                f"'{name}' already exists for this business."
            )

        return name

    def validate_default_price(self, value):
        if value is not None and value < 0:
            raise serializers.ValidationError("Price cannot be negative.")
        return value
