import uuid
from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.db import models
from pgvector.django import VectorField


class Conversation(models.Model):
    class Type(models.TextChoices):
        PHONE_CALL = "phone_call", "Phone Call"
        IN_PERSON = "in_person", "In Person"
        VIDEO_CALL = "video_call", "Video Call"
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"
        OTHER = "other", "Other"

    class Sentiment(models.TextChoices):
        VERY_NEGATIVE = "very_negative", "Very Negative"
        NEGATIVE = "negative", "Negative"
        NEUTRAL = "neutral", "Neutral"
        POSITIVE = "positive", "Positive"
        VERY_POSITIVE = "very_positive", "Very Positive"

    class AIStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="conversations",
    )
    conversation_type = models.CharField(max_length=20, choices=Type.choices)
    raw_text = models.TextField()

    # AI extracted fields
    ai_summary = models.TextField(blank=True, null=True)
    customer_requirements = models.TextField(blank=True, null=True)
    pain_points = models.TextField(blank=True, null=True)
    pricing_discussion = models.TextField(blank=True, null=True)
    next_steps = models.TextField(blank=True, null=True)

    # Sentiment
    sentiment = models.CharField(
        max_length=20, choices=Sentiment.choices, blank=True, null=True
    )
    sentiment_score = models.FloatField(blank=True, null=True)

    # Array fields (PostgreSQL-specific)
    topics = ArrayField(models.CharField(max_length=100), default=list, blank=True)
    competitor_mentions = ArrayField(models.CharField(max_length=100), default=list, blank=True)

    # Vector embedding (384-dim for all-MiniLM-L6-v2)
    embedding = VectorField(dimensions=384, blank=True, null=True)

    # Pipeline status
    ai_status = models.CharField(
        max_length=20, choices=AIStatus.choices, default=AIStatus.PENDING
    )

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="conversations",
    )
    interaction_date = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Soft delete
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "conversations_conversation"
        ordering = ["-interaction_date"]
        indexes = [
            models.Index(fields=["customer"]),
            models.Index(fields=["created_by"]),
            models.Index(fields=["interaction_date"]),
            models.Index(fields=["sentiment"]),
            models.Index(fields=["ai_status"]),
            models.Index(fields=["is_deleted"]),
        ]

    def __str__(self):
        return f"{self.get_conversation_type_display()} with {self.customer} on {self.interaction_date:%Y-%m-%d}"


class ActionItem(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="action_items"
    )
    description = models.TextField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="action_items",
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    priority = models.CharField(
        max_length=10, choices=Priority.choices, default=Priority.MEDIUM
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "conversations_actionitem"
        ordering = ["-priority", "due_date"]
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["assigned_to"]),
            models.Index(fields=["due_date"]),
        ]

    def __str__(self):
        return f"[{self.priority}] {self.description[:60]}"


class Attachment(models.Model):
    class FileType(models.TextChoices):
        AUDIO = "audio", "Audio"
        IMAGE = "image", "Image"
        DOCUMENT = "document", "Document"
        RECORDING = "recording", "Recording"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="attachments"
    )
    file_type = models.CharField(max_length=20, choices=FileType.choices)
    file = models.FileField(upload_to="attachments/%Y/%m/")
    original_filename = models.CharField(max_length=255)
    transcription = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "conversations_attachment"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.file_type}: {self.original_filename}"
