from django.contrib import admin
from .models import ZohoCredential


@admin.register(ZohoCredential)
class ZohoCredentialAdmin(admin.ModelAdmin):
    list_display = ["user", "zoho_user_email", "last_sync_at", "expires_at", "created_at"]
    readonly_fields = ["access_token", "refresh_token", "expires_at", "zoho_org_id", "created_at", "updated_at"]
    search_fields = ["user__email", "zoho_user_email"]
