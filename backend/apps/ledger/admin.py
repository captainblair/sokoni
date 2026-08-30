from django.contrib import admin

from apps.ledger.models import Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "occurred_at",
        "business",
        "transaction_type",
        "amount",
        "payment_status",
        "payment_method",
        "party",
        "source",
        "is_active",
    ]
    list_filter = ["transaction_type", "payment_status", "payment_method", "source", "is_active"]
    search_fields = ["description", "notes", "reference", "business__name", "party__name"]
    readonly_fields = ["id", "created_at", "updated_at", "created_by"]
    autocomplete_fields = ["business", "party", "product"]
    date_hierarchy = "occurred_at"
