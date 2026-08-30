from django.contrib import admin

from apps.audit.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ["created_at", "business", "action", "object_type", "summary", "actor"]
    list_filter = ["action", "object_type", "source"]
    search_fields = ["summary", "business__name", "actor__email"]
    readonly_fields = [
        "id",
        "created_at",
        "business",
        "actor",
        "action",
        "object_type",
        "object_id",
        "summary",
        "before",
        "after",
        "source",
        "extra",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
