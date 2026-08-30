from django.contrib import admin

from apps.parties.models import Party


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "party_type", "phone_number", "is_active"]
    list_filter = ["party_type", "is_active"]
    search_fields = ["name", "phone_number", "business__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    autocomplete_fields = ["business"]
