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
        return (
            ActionItem.objects.filter(conversation__is_deleted=False)
            .select_related("assigned_to", "conversation__customer")
        )

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
