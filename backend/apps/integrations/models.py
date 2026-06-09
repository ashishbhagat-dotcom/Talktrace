from django.conf import settings
from django.db import models
from django.utils import timezone


class ZohoCredential(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="zoho_credential",
    )
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    zoho_user_email = models.EmailField(blank=True)
    zoho_org_id = models.CharField(max_length=100, blank=True)
    # Track last sync to do incremental pulls
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrations_zoho_credential"

    def __str__(self):
        return f"Zoho credential for {self.user.email}"

    @property
    def is_token_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_connected(self):
        return bool(self.access_token and self.refresh_token)


class GmailCredential(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="gmail_credential",
    )
    access_token = models.TextField()
    refresh_token = models.TextField()
    expires_at = models.DateTimeField()
    gmail_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integrations_gmail_credential"

    def __str__(self):
        return f"Gmail credential for {self.user.email}"

    @property
    def is_token_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_connected(self):
        return bool(self.access_token and self.refresh_token)
