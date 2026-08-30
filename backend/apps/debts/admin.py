from django.contrib import admin

from apps.debts.models import Debt, DebtPayment


class DebtPaymentInline(admin.TabularInline):
    model = DebtPayment
    extra = 0
    readonly_fields = ["created_at"]


@admin.register(Debt)
class DebtAdmin(admin.ModelAdmin):
    list_display = [
        "party",
        "business",
        "debt_type",
        "original_amount",
        "amount_paid",
        "status",
        "due_date",
    ]
    list_filter = ["debt_type", "status", "source"]
    search_fields = ["party__name", "description", "notes", "business__name"]
    readonly_fields = ["id", "created_at", "updated_at", "amount_paid"]
    autocomplete_fields = ["business", "party"]
    inlines = [DebtPaymentInline]


@admin.register(DebtPayment)
class DebtPaymentAdmin(admin.ModelAdmin):
    list_display = ["debt", "amount", "paid_at", "payment_method", "source"]
    list_filter = ["payment_method", "source"]
    readonly_fields = ["id", "created_at", "updated_at"]
