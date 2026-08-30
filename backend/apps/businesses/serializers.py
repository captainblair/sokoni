from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.businesses.models import Business, Membership, MembershipRole

User = get_user_model()


class BusinessSerializer(serializers.ModelSerializer):
    my_role = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Business
        fields = [
            "id",
            "name",
            "business_type",
            "currency",
            "location",
            "phone_number",
            "description",
            "my_role",
            "member_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_my_role(self, obj):
        membership = obj.membership_for(self.context["request"].user)
        return membership.role if membership else None

    def get_member_count(self, obj):
        return obj.memberships.count()


class MembershipSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user_id", "email", "full_name", "role", "created_at"]
        read_only_fields = ["id", "user_id", "email", "full_name", "created_at"]


class MembershipCreateSerializer(serializers.Serializer):
    """Adds an existing Sokoni account to a business by email address."""

    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=MembershipRole.choices, default=MembershipRole.MEMBER
    )

    def validate_email(self, value):
        email = value.lower().strip()
        user = User.objects.filter(email=email).first()
        if user is None:
            raise serializers.ValidationError("No Sokoni account exists with this email.")
        self.context["invited_user"] = user
        return email

    def validate(self, attrs):
        business = self.context["business"]
        user = self.context["invited_user"]

        if business.memberships.filter(user=user).exists():
            raise serializers.ValidationError(
                {"email": "This user is already a member of the business."}
            )
        return attrs

    def create(self, validated_data):
        return Membership.objects.create(
            business=self.context["business"],
            user=self.context["invited_user"],
            role=validated_data["role"],
            invited_by=self.context["request"].user,
        )


class MembershipRoleUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=MembershipRole.choices)
