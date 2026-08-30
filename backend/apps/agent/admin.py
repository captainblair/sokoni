from django.contrib import admin

from apps.agent.models import PendingAction


@admin.register(PendingAction)
class PendingActionAdmin(admin.ModelAdmin):
    list_display = ["tool", "business", "user", "reason", "expires_at", "consumed_at"]
    list_filter = ["tool", "reason"]
    search_fields = ["question", "business__name", "user__email"]
    readonly_fields = [
        "id",
        "token",
        "tool",
        "parameters",
        "question",
        "reason",
        "confidence",
        "expires_at",
        "consumed_at",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        # Pending actions are raised by the agent layer, never typed in by hand.
        return False
