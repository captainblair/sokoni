from django.contrib import admin

from apps.businesses.models import Business, Membership


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ["user"]
    readonly_fields = ["created_at"]


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ["name", "business_type", "currency", "location", "is_active", "created_at"]
    list_filter = ["business_type", "is_active", "currency"]
    search_fields = ["name", "location", "phone_number"]
    readonly_fields = ["id", "created_at", "updated_at"]
    inlines = [MembershipInline]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "business", "role", "created_at"]
    list_filter = ["role"]
    search_fields = ["user__email", "business__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    autocomplete_fields = ["user", "business"]
