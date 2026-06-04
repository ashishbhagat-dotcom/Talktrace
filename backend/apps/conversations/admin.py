from django.contrib import admin
from .models import ActionItem, Attachment, Conversation


class ActionItemInline(admin.TabularInline):
    model = ActionItem
    extra = 0
    fields = ["description", "assigned_to", "due_date", "status", "priority"]


class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0
    fields = ["file_type", "original_filename", "file"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = [
        "customer", "conversation_type", "sentiment", "ai_status",
        "created_by", "interaction_date", "created_at",
    ]
    list_filter = ["conversation_type", "sentiment", "ai_status", "is_deleted"]
    search_fields = ["customer__name", "raw_text", "ai_summary"]
    ordering = ["-interaction_date"]
    exclude = ["embedding"]  # numpy array breaks admin rendering
    readonly_fields = [
        "ai_summary", "customer_requirements", "pain_points",
        "pricing_discussion", "next_steps", "sentiment", "sentiment_score",
        "topics", "competitor_mentions", "ai_status", "embedding_preview",
    ]
    inlines = [ActionItemInline, AttachmentInline]

    def embedding_preview(self, obj):
        if obj.embedding is None:
            return "Not generated"
        return f"384-dim vector (generated)"
    embedding_preview.short_description = "Embedding"


@admin.register(ActionItem)
class ActionItemAdmin(admin.ModelAdmin):
    list_display = [
        "description_short", "conversation", "assigned_to",
        "due_date", "status", "priority",
    ]
    list_filter = ["status", "priority"]
    search_fields = ["description", "conversation__customer__name"]

    def description_short(self, obj):
        return obj.description[:60]
    description_short.short_description = "Description"
