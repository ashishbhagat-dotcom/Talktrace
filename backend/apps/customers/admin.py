from django.contrib import admin
from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "email", "type", "created_at"]
    list_filter = ["type"]
    search_fields = ["name", "email", "company"]
    ordering = ["name"]
