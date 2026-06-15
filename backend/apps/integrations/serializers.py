from django.utils import timezone
from rest_framework import serializers

from apps.conversations.models import Attachment

from .models import CRMDraft
from .services.zoho_fields import (
    extraction_fields,
    get_schema,
    module_for_record_type,
    required_fields,
)


class CRMDraftCreateSerializer(serializers.Serializer):
    """Accepts the conversation input + record type to start a new draft."""

    record_type = serializers.ChoiceField(choices=CRMDraft.RecordType.choices)
    raw_text = serializers.CharField(required=False, allow_blank=True, default="")
    attachment_id = serializers.UUIDField(required=False, allow_null=True)

    def validate(self, data):
        if not data.get("raw_text") and not data.get("attachment_id"):
            raise serializers.ValidationError(
                "Provide either raw_text or attachment_id."
            )
        return data

    def validate_attachment_id(self, value):
        if value and not Attachment.objects.filter(id=value).exists():
            raise serializers.ValidationError("Attachment not found.")
        return value


class CRMDraftSerializer(serializers.ModelSerializer):
    """Full draft representation including the live field schema for the record type."""

    schema = serializers.SerializerMethodField()
    required = serializers.SerializerMethodField()
    extraction_field_order = serializers.SerializerMethodField()
    missing_required = serializers.SerializerMethodField()

    class Meta:
        model = CRMDraft
        fields = [
            "id", "record_type", "status",
            "raw_text", "attachment",
            "extracted_fields", "ai_summary", "action_items",
            "topics", "confidence",
            "zoho_record_id", "zoho_note_id", "error_message",
            "edit_log",
            "schema", "required", "extraction_field_order", "missing_required",
            "created_at", "updated_at", "submitted_at",
        ]
        read_only_fields = fields  # writes go through the update serializer

    def _schema_for(self, obj):
        """Cached schema lookup per request, keyed by (user_id, record_type)."""
        if not hasattr(self, "_schema_cache"):
            self._schema_cache = {}
        key = (obj.created_by_id, obj.record_type)
        if key in self._schema_cache:
            return self._schema_cache[key]

        from .models import ZohoCredential

        cred = ZohoCredential.objects.filter(user_id=obj.created_by_id).first()
        if not cred:
            cred = ZohoCredential.objects.filter(user__role="admin").first()
        if not cred:
            self._schema_cache[key] = {}
            return {}
        schema = get_schema(cred, module_for_record_type(obj.record_type))
        self._schema_cache[key] = schema
        return schema

    def get_schema(self, obj):
        return self._schema_for(obj)

    def get_required(self, obj):
        return required_fields(self._schema_for(obj))

    def get_extraction_field_order(self, obj):
        schema = self._schema_for(obj)
        order = list(extraction_fields(obj.record_type))
        for r in required_fields(schema):
            if r not in order:
                order.append(r)
        return [
            api for api in order
            if api in schema and not schema[api].get("read_only")
        ]

    def get_missing_required(self, obj):
        schema = self._schema_for(obj)
        return [
            api for api in required_fields(schema)
            if not (obj.extracted_fields or {}).get(api)
        ]


class CRMDraftUpdateSerializer(serializers.Serializer):
    """Patch the extracted_fields dict. Appends to edit_log."""

    extracted_fields = serializers.DictField(child=serializers.JSONField(allow_null=True))

    def update(self, instance: CRMDraft, validated_data):
        new_fields = validated_data["extracted_fields"]
        old = instance.extracted_fields or {}
        log = list(instance.edit_log or [])
        now = timezone.now().isoformat()

        merged = dict(old)
        for k, v in new_fields.items():
            if v in (None, ""):
                if k in merged:
                    log.append({"field": k, "old": merged[k], "new": None, "at": now})
                    merged.pop(k, None)
            else:
                if merged.get(k) != v:
                    log.append({"field": k, "old": merged.get(k), "new": v, "at": now})
                    merged[k] = v

        instance.extracted_fields = merged
        instance.edit_log = log
        instance.save(update_fields=["extracted_fields", "edit_log", "updated_at"])
        return instance
