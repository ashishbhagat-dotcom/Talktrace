from rest_framework import serializers
from apps.accounts.serializers import UserMinimalSerializer
from apps.customers.serializers import CustomerMinimalSerializer
from .models import ActionItem, Attachment, Conversation


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ["id", "file_type", "file", "original_filename", "transcription", "created_at"]
        read_only_fields = ["id", "created_at"]


class ActionItemSerializer(serializers.ModelSerializer):
    assigned_to = UserMinimalSerializer(read_only=True)
    assigned_to_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    conversation_id = serializers.UUIDField(source="conversation.id", read_only=True)

    class Meta:
        model = ActionItem
        fields = [
            "id", "conversation_id", "description", "assigned_to", "assigned_to_id",
            "due_date", "status", "priority", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ConversationListSerializer(serializers.ModelSerializer):
    customer = CustomerMinimalSerializer(read_only=True)
    created_by = UserMinimalSerializer(read_only=True)
    summary_preview = serializers.SerializerMethodField()
    pending_actions_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id", "customer", "conversation_type", "summary_preview",
            "sentiment", "sentiment_score", "topics", "ai_status",
            "created_by", "interaction_date", "created_at", "pending_actions_count",
        ]

    def get_summary_preview(self, obj):
        if obj.ai_summary:
            return obj.ai_summary[:200]
        return obj.raw_text[:200]


class ConversationDetailSerializer(serializers.ModelSerializer):
    customer = CustomerMinimalSerializer(read_only=True)
    customer_id = serializers.UUIDField(write_only=True)
    created_by = UserMinimalSerializer(read_only=True)
    action_items = ActionItemSerializer(many=True, read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Conversation
        fields = [
            "id", "customer", "customer_id", "conversation_type", "raw_text",
            "ai_summary", "customer_requirements", "pain_points",
            "pricing_discussion", "next_steps",
            "sentiment", "sentiment_score", "topics", "competitor_mentions",
            "ai_status", "created_by", "interaction_date",
            "created_at", "updated_at",
            "action_items", "attachments",
            "gmail_thread_id",
        ]
        read_only_fields = [
            "id", "ai_summary", "customer_requirements", "pain_points",
            "pricing_discussion", "next_steps", "sentiment", "sentiment_score",
            "topics", "competitor_mentions", "ai_status", "created_by",
            "created_at", "updated_at",
        ]

    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ConversationStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "ai_status", "raw_text", "updated_at"]
