import logging
from django.conf import settings
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from common.pagination import StandardResultsPagination
from .filters import ActionItemFilter, ConversationFilter
from .models import ActionItem, Attachment, Conversation
from .serializers import (
    ActionItemSerializer,
    ConversationDetailSerializer,
    ConversationListSerializer,
    ConversationStatusSerializer,
)

logger = logging.getLogger(__name__)


class ConversationViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = StandardResultsPagination
    filterset_class = ConversationFilter

    def get_queryset(self):
        qs = (
            Conversation.objects.filter(is_deleted=False)
            .select_related("customer", "created_by")
            .annotate(
                pending_actions_count=Count(
                    "action_items", filter=Q(action_items__status="pending")
                )
            )
        )
        # Members see only their own conversations; admins and managers see all
        if self.request.user.role == "member":
            qs = qs.filter(created_by=self.request.user)
        return qs

    def get_serializer_class(self):
        if self.action in ["list"]:
            return ConversationListSerializer
        return ConversationDetailSerializer

    def perform_create(self, serializer):
        conversation = serializer.save(
            created_by=self.request.user,
            ai_status=Conversation.AIStatus.PENDING,
        )
        self._trigger_ai_pipeline(conversation)

    def _trigger_ai_pipeline(self, conversation):
        try:
            from .tasks import trigger_ai_pipeline
            trigger_ai_pipeline(str(conversation.id))
        except Exception as e:
            logger.error(f"Failed to trigger AI pipeline for {conversation.id}: {e}")

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save(update_fields=["is_deleted"])

    @action(detail=True, methods=["get"], url_path="status")
    def ai_status(self, request, pk=None):
        conversation = self.get_object()
        return Response(ConversationStatusSerializer(conversation).data)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        """Apply final user edits to the AI fields and push to Zoho.

        Body (all optional): ai_summary, customer_requirements, pain_points,
        pricing_discussion, next_steps, sentiment, topics (list),
        competitor_mentions (list), action_items (list of
        {id?, description, due_date?, priority?, status?}).
        """
        conversation = self.get_object()

        if conversation.ai_status not in (
            Conversation.AIStatus.READY_FOR_REVIEW,
            Conversation.AIStatus.FAILED,
            Conversation.AIStatus.COMPLETED,
        ):
            return Response(
                {"error": f"Cannot confirm from status '{conversation.ai_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        editable_text_fields = [
            "ai_summary", "customer_requirements", "pain_points",
            "pricing_discussion", "next_steps", "sentiment",
        ]
        updates = {}
        for f in editable_text_fields:
            if f in request.data:
                updates[f] = request.data.get(f) or ""

        for f in ("topics", "competitor_mentions"):
            if f in request.data:
                val = request.data.get(f) or []
                if isinstance(val, list):
                    updates[f] = val

        if updates:
            for k, v in updates.items():
                setattr(conversation, k, v)
            conversation.save(update_fields=[*updates.keys(), "updated_at"])

        # Sync action item edits (upsert/delete)
        if "action_items" in request.data:
            from .models import ActionItem
            incoming = request.data.get("action_items") or []
            incoming = [a for a in incoming if isinstance(a, dict)]
            keep_ids = set()
            for item in incoming:
                desc = (item.get("description") or "").strip()
                if not desc:
                    continue
                payload = {
                    "description": desc[:500],
                    "due_date": item.get("due_date") or None,
                    "priority": item.get("priority", "medium"),
                    "status": item.get("status", "pending"),
                }
                if item.get("id"):
                    obj, _ = ActionItem.objects.update_or_create(
                        id=item["id"], conversation=conversation, defaults=payload,
                    )
                else:
                    obj = ActionItem.objects.create(conversation=conversation, **payload)
                keep_ids.add(str(obj.id))
            # Delete action items the user removed
            ActionItem.objects.filter(conversation=conversation).exclude(id__in=keep_ids).delete()

        # Mark completed and queue Zoho push (note + a Task per action item)
        conversation.ai_status = Conversation.AIStatus.COMPLETED
        conversation.save(update_fields=["ai_status", "updated_at"])

        from apps.integrations.tasks import push_action_item_to_zoho, push_conversation_to_zoho
        if conversation.created_by_id:
            push_conversation_to_zoho.delay(str(conversation.id), str(conversation.created_by_id))

        # Push the final action items set (after the user's edits) as Zoho Tasks
        from .models import ActionItem
        for item_id in ActionItem.objects.filter(conversation=conversation).values_list("id", flat=True):
            push_action_item_to_zoho.delay(str(item_id))

        return Response(ConversationDetailSerializer(conversation, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="analyze")
    def analyze(self, request, pk=None):
        """Kick off the extraction pipeline. Used after the user reviews the
        Whisper transcript on an audio-sourced conversation. Optionally
        accepts an updated `raw_text` so user edits to the transcript are saved.
        """
        from .tasks import trigger_extraction
        conversation = self.get_object()

        if conversation.ai_status not in (
            Conversation.AIStatus.TRANSCRIBED,
            Conversation.AIStatus.FAILED,
            Conversation.AIStatus.PENDING,
        ):
            return Response(
                {"error": f"Cannot analyze from status '{conversation.ai_status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        new_text = request.data.get("raw_text")
        if new_text is not None:
            conversation.raw_text = new_text
            conversation.save(update_fields=["raw_text", "updated_at"])

        if not (conversation.raw_text or "").strip():
            return Response(
                {"error": "Transcript is empty. Add text first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        trigger_extraction(str(conversation.id))
        conversation.refresh_from_db()
        return Response(ConversationStatusSerializer(conversation).data)

    @action(detail=False, methods=["post"], url_path="from-gmail")
    def import_from_gmail(self, request):
        from apps.integrations.models import GmailCredential
        from apps.integrations.services import gmail_client as gc

        thread_id = request.data.get("thread_id")
        customer_id = request.data.get("customer_id")
        conversation_type = request.data.get("conversation_type", "email")
        interaction_date = request.data.get("interaction_date")

        if not thread_id or not customer_id:
            return Response(
                {"error": "thread_id and customer_id are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            cred = GmailCredential.objects.get(user=request.user)
        except GmailCredential.DoesNotExist:
            return Response(
                {"error": "Gmail not connected. Connect Gmail in Settings first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            access_token = gc.get_valid_token(cred)
            thread = gc.get_thread(access_token, thread_id)
        except Exception as e:
            logger.error(f"Failed to fetch Gmail thread {thread_id}: {e}")
            return Response({"error": "Failed to fetch thread from Gmail"}, status=status.HTTP_502_BAD_GATEWAY)

        conversation = Conversation.objects.create(
            customer_id=customer_id,
            conversation_type=conversation_type,
            raw_text=thread["raw_text"],
            gmail_thread_id=thread_id,
            created_by=request.user,
            ai_status=Conversation.AIStatus.PENDING,
            interaction_date=interaction_date or timezone.now(),
        )

        try:
            from .tasks import trigger_ai_pipeline
            trigger_ai_pipeline(str(conversation.id))
        except Exception as e:
            logger.error(f"Failed to trigger AI pipeline for gmail import {conversation.id}: {e}")

        return Response(
            ConversationDetailSerializer(conversation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="voice",
        parser_classes=[MultiPartParser, FormParser],
    )
    def voice_upload(self, request):
        audio_file = request.FILES.get("audio")
        customer_id = request.data.get("customer_id")
        conversation_type = request.data.get("conversation_type", "phone_call")
        interaction_date = request.data.get("interaction_date")

        if not audio_file:
            return Response(
                {"error": "audio file is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file type
        content_type = audio_file.content_type
        if content_type not in settings.ALLOWED_AUDIO_TYPES:
            return Response(
                {"error": f"Unsupported audio type: {content_type}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate file size
        if audio_file.size > settings.AUDIO_UPLOAD_MAX_SIZE:
            return Response(
                {"error": "Audio file must be under 50MB"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        conversation = Conversation.objects.create(
            customer_id=customer_id,
            conversation_type=conversation_type,
            raw_text="",
            created_by=request.user,
            ai_status=Conversation.AIStatus.PENDING,
            interaction_date=interaction_date or timezone.now(),
        )

        attachment = Attachment.objects.create(
            conversation=conversation,
            file_type=Attachment.FileType.AUDIO,
            file=audio_file,
            original_filename=audio_file.name,
        )

        try:
            from .tasks import trigger_ai_pipeline
            trigger_ai_pipeline(str(conversation.id), attachment_id=str(attachment.id))
        except Exception as e:
            logger.error(f"Failed to trigger AI pipeline for voice upload {conversation.id}: {e}")

        return Response(
            ConversationDetailSerializer(conversation, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class ActionItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ActionItemSerializer
    pagination_class = StandardResultsPagination
    filterset_class = ActionItemFilter
    http_method_names = ["get", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = (
            ActionItem.objects.filter(conversation__is_deleted=False)
            .select_related("assigned_to", "conversation__customer")
        )
        if self.request.user.role == "member":
            qs = qs.filter(conversation__created_by=self.request.user)
        return qs

    def perform_update(self, serializer):
        assigned_to_id = serializer.validated_data.pop("assigned_to_id", None)
        if assigned_to_id is not None:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                user = User.objects.get(id=assigned_to_id)
                serializer.save(assigned_to=user)
            except User.DoesNotExist:
                serializer.save(assigned_to=None)
        else:
            serializer.save()

    @action(detail=False, methods=["get"], url_path="my")
    def my_items(self, request):
        qs = self.get_queryset().filter(assigned_to=request.user)
        qs = self.filter_queryset(qs)
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)

    @action(detail=False, methods=["get"], url_path="overdue")
    def overdue(self, request):
        qs = self.get_queryset().filter(
            due_date__lt=timezone.now().date()
        ).exclude(status__in=["completed", "cancelled"])
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(self.get_serializer(page, many=True).data)
        return Response(self.get_serializer(qs, many=True).data)
