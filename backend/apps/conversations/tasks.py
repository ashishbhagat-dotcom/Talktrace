import logging

from celery import chain, shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, name="conversations.transcribe_audio")
def transcribe_audio(self, conversation_id: str, attachment_id: str):
    from .models import Attachment, Conversation
    from .services.transcription_service import transcribe_attachment

    try:
        attachment = Attachment.objects.select_related("conversation").get(id=attachment_id)
        conversation = attachment.conversation

        Conversation.objects.filter(id=conversation_id).update(ai_status="processing")

        transcript = transcribe_attachment(attachment)
        attachment.transcription = transcript
        attachment.save(update_fields=["transcription"])

        conversation.raw_text = transcript
        conversation.save(update_fields=["raw_text"])

        logger.info(f"Transcription complete for conversation {conversation_id}")
    except Exception as exc:
        logger.error(f"Transcription failed for {conversation_id}: {exc}")
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@shared_task(bind=True, max_retries=3, name="conversations.extract_with_llm")
def extract_with_llm(self, conversation_id: str):
    from .models import ActionItem, Conversation
    from .services.ai_service import extract_structured_data

    try:
        conversation = Conversation.objects.select_related("customer").get(id=conversation_id)

        if not conversation.raw_text:
            logger.warning(f"No raw_text for conversation {conversation_id}, skipping LLM")
            return

        Conversation.objects.filter(id=conversation_id).update(ai_status="processing")

        result = extract_structured_data(conversation.raw_text)

        # Bulk-update conversation fields
        Conversation.objects.filter(id=conversation_id).update(
            ai_summary=result["summary"],
            customer_requirements=result["customer_requirements"],
            pain_points=result["pain_points"],
            pricing_discussion=result["pricing_discussion"],
            next_steps=result["next_steps"],
            sentiment=result["sentiment"],
            sentiment_score=result["sentiment_score"],
            topics=result["topics"],
            competitor_mentions=result["competitor_mentions"],
        )

        # Create ActionItems from extracted data
        action_items = result.get("action_items", [])
        if action_items:
            ActionItem.objects.bulk_create([
                ActionItem(
                    conversation_id=conversation_id,
                    description=item["description"],
                    due_date=item.get("due_date"),
                    priority=item.get("priority", "medium"),
                )
                for item in action_items
                if item.get("description")
            ])

        logger.info(f"LLM extraction complete for conversation {conversation_id}")
    except Exception as exc:
        logger.error(f"LLM extraction failed for {conversation_id}: {exc}")
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@shared_task(bind=True, max_retries=2, name="conversations.generate_embedding")
def generate_embedding(self, conversation_id: str):
    from .models import Conversation
    from .services.embedding_service import generate_embedding as _generate

    try:
        conversation = Conversation.objects.get(id=conversation_id)
        text = conversation.ai_summary or conversation.raw_text
        embedding = _generate(text)

        if embedding:
            Conversation.objects.filter(id=conversation_id).update(embedding=embedding)
            logger.info(f"Embedding generated for conversation {conversation_id}")
    except Exception as exc:
        logger.error(f"Embedding generation failed for {conversation_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@shared_task(bind=True, max_retries=2, name="conversations.index_in_elasticsearch")
def index_in_elasticsearch(self, conversation_id: str):
    from .models import Conversation
    from .services.search_service import index_conversation

    try:
        conversation = Conversation.objects.select_related("customer", "created_by").get(
            id=conversation_id
        )
        index_conversation(conversation)
        logger.info(f"Indexed conversation {conversation_id} in Elasticsearch")
    except Exception as exc:
        logger.error(f"ES indexing failed for {conversation_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@shared_task(name="conversations.mark_pipeline_failed")
def mark_pipeline_failed(request, exc, traceback, conversation_id: str):
    from .models import Conversation
    logger.error(f"AI pipeline failed for conversation {conversation_id}: {exc}")
    Conversation.objects.filter(id=conversation_id).update(ai_status="failed")


@shared_task(bind=True, name="conversations.complete_pipeline")
def complete_pipeline(self, conversation_id: str):
    from .models import Conversation
    conversation = Conversation.objects.select_related("created_by").get(id=conversation_id)
    Conversation.objects.filter(id=conversation_id).update(ai_status="completed")
    logger.info(f"AI pipeline completed for conversation {conversation_id}")

    # Push summary to Zoho if creator is connected
    if conversation.created_by_id:
        from apps.integrations.tasks import push_conversation_to_zoho
        push_conversation_to_zoho.delay(conversation_id, str(conversation.created_by_id))


def trigger_ai_pipeline(conversation_id: str, attachment_id: str = None):
    from .models import Conversation

    Conversation.objects.filter(id=conversation_id).update(ai_status="pending")

    tasks = []
    if attachment_id:
        tasks.append(transcribe_audio.si(conversation_id, attachment_id))

    tasks.extend([
        extract_with_llm.si(conversation_id),
        generate_embedding.si(conversation_id),
        index_in_elasticsearch.si(conversation_id),
        complete_pipeline.si(conversation_id),
    ])

    pipeline = chain(*tasks)
    pipeline.apply_async(
        link_error=mark_pipeline_failed.s(conversation_id=conversation_id),
    )
    logger.info(f"AI pipeline triggered for conversation {conversation_id}")
