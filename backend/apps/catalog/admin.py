from django.contrib import admin

from apps.catalog.models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "business", "unit", "default_price", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "unit", "business__name"]
    readonly_fields = ["id", "created_at", "updated_at"]
    autocomplete_fields = ["business"]
