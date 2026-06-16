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

        # Use 'transcribing' so the UI shows only the Transcribing step active
        # while Whisper is running. 'processing' is reserved for the LLM
        # extraction phase that comes after the user reviews the transcript.
        Conversation.objects.filter(id=conversation_id).update(ai_status="transcribing")

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
            created_items = ActionItem.objects.bulk_create([
                ActionItem(
                    conversation_id=conversation_id,
                    description=item["description"],
                    due_date=item.get("due_date"),
                    priority=item.get("priority", "medium"),
                )
                for item in action_items
                if item.get("description")
            ])
            from apps.integrations.tasks import push_action_item_to_zoho
            for item in created_items:
                push_action_item_to_zoho.delay(str(item.id))

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
    """Mark AI extraction done. The conversation now waits for the user to
    review AI-generated fields before pushing anything to Zoho. The user
    confirms (and optionally edits) via POST /conversations/<id>/confirm/.
    """
    from .models import Conversation
    Conversation.objects.filter(id=conversation_id).update(ai_status="ready_for_review")
    logger.info(f"AI pipeline ready for review on conversation {conversation_id}")


@shared_task(bind=True, name="conversations.mark_transcribed")
def mark_transcribed(self, conversation_id: str):
    """Set ai_status to 'transcribed' so the user can review the transcript
    before the extraction chain runs."""
    from .models import Conversation
    Conversation.objects.filter(id=conversation_id).update(ai_status="transcribed")
    logger.info(f"Conversation {conversation_id} transcribed; waiting for user review")


def trigger_transcription(conversation_id: str, attachment_id: str):
    """Audio path step 1: transcribe and pause. User reviews transcript,
    then calls trigger_extraction() to run the rest of the pipeline.
    """
    from .models import Conversation

    Conversation.objects.filter(id=conversation_id).update(ai_status="transcribing")

    pipeline = chain(
        transcribe_audio.si(conversation_id, attachment_id),
        mark_transcribed.si(conversation_id),
    )
    pipeline.apply_async(
        link_error=mark_pipeline_failed.s(conversation_id=conversation_id),
    )
    logger.info(f"Transcription triggered for conversation {conversation_id}")


def trigger_extraction(conversation_id: str):
    """Run the AI extraction chain on an existing transcript. Used both for
    text-input conversations and for the post-transcript-review audio path.
    """
    from .models import Conversation

    Conversation.objects.filter(id=conversation_id).update(ai_status="processing")

    pipeline = chain(
        extract_with_llm.si(conversation_id),
        generate_embedding.si(conversation_id),
        index_in_elasticsearch.si(conversation_id),
        complete_pipeline.si(conversation_id),
    )
    pipeline.apply_async(
        link_error=mark_pipeline_failed.s(conversation_id=conversation_id),
    )
    logger.info(f"AI extraction triggered for conversation {conversation_id}")


def trigger_ai_pipeline(conversation_id: str, attachment_id: str = None):
    """Legacy single-shot entry. Routes audio through the two-step flow
    (transcribe → wait for review) and text through extraction directly.
    """
    if attachment_id:
        trigger_transcription(conversation_id, attachment_id)
    else:
        trigger_extraction(conversation_id)
