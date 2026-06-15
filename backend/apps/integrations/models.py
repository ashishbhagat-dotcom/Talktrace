import uuid

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
    # Cached field schemas per module (Leads, Accounts) with picklist values
    field_schema_cache = models.JSONField(default=dict, blank=True)
    field_schema_fetched_at = models.DateTimeField(null=True, blank=True)
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


class CRMDraft(models.Model):
    """A draft Lead/Account record being built from a conversation.

    Lifecycle: pending → extracting → ready (user reviews) → submitted (Zoho record created).
    """

    class RecordType(models.TextChoices):
        LEAD = "lead", "Lead"
        ACCOUNT = "account", "Account"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        EXTRACTING = "extracting", "Extracting"
        READY = "ready", "Ready for Review"
        SUBMITTED = "submitted", "Submitted"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="crm_drafts",
    )
    record_type = models.CharField(max_length=20, choices=RecordType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Source content
    raw_text = models.TextField(blank=True)
    attachment = models.ForeignKey(
        "conversations.Attachment",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="crm_drafts",
    )

    # AI extraction output
    extracted_fields = models.JSONField(default=dict, blank=True)
    ai_summary = models.TextField(blank=True)
    action_items = models.JSONField(default=list, blank=True)
    topics = models.JSONField(default=list, blank=True)
    confidence = models.JSONField(default=dict, blank=True)

    # Post-submit linkage
    zoho_record_id = models.CharField(max_length=64, blank=True)
    zoho_note_id = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)

    # Audit: list of {field, old, new, at}
    edit_log = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "integrations_crm_draft"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_by", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.get_record_type_display()} draft by {self.created_by_id} ({self.status})"
