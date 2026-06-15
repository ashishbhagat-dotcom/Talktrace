import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="integrations.sync_all_zoho_credentials")
def sync_all_zoho_credentials():
    """Periodic task: sync Zoho contacts/leads for all connected users."""
    from .models import ZohoCredential
    from .services.zoho_sync import sync_from_zoho

    credentials = ZohoCredential.objects.select_related("user").all()
    total = {"created": 0, "updated": 0, "errors": 0}

    for credential in credentials:
        try:
            counts = sync_from_zoho(credential)
            for k in total:
                total[k] += counts.get(k, 0)
        except Exception as e:
            logger.error(f"Zoho sync failed for user {credential.user_id}: {e}")
            total["errors"] += 1

    logger.info(f"Zoho periodic sync complete: {total}")
    return total


@shared_task(name="integrations.sync_zoho_for_user", bind=True, max_retries=2)
def sync_zoho_for_user(self, user_id: int):
    """Sync Zoho data for a single user (manual or on-demand)."""
    from .models import ZohoCredential
    from .services.zoho_sync import sync_from_zoho

    try:
        credential = ZohoCredential.objects.get(user_id=user_id)
        return sync_from_zoho(credential)
    except ZohoCredential.DoesNotExist:
        logger.warning(f"No Zoho credential for user {user_id}")
        return {}
    except Exception as exc:
        logger.error(f"Zoho sync failed for user {user_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name="integrations.push_action_item_to_zoho", bind=True, max_retries=2)
def push_action_item_to_zoho(self, action_item_id: str):
    """Push an ActionItem as a Task in Zoho CRM.

    Uses the rep's own token if connected, falls back to any admin token.
    """
    from apps.conversations.models import ActionItem
    from .models import ZohoCredential
    from .services.zoho_sync import push_action_item_task

    try:
        action_item = ActionItem.objects.select_related(
            "conversation__customer", "conversation__created_by"
        ).get(id=action_item_id)

        credential = None
        if action_item.conversation.created_by_id:
            credential = ZohoCredential.objects.filter(
                user_id=action_item.conversation.created_by_id
            ).first()
        if not credential:
            credential = ZohoCredential.objects.filter(user__role="admin").first()
        if not credential:
            return  # nobody connected to Zoho

        task_id = push_action_item_task(action_item, credential)
        if task_id:
            ActionItem.objects.filter(id=action_item_id).update(zoho_task_id=task_id)
    except Exception as exc:
        logger.error(f"Zoho task push failed for action item {action_item_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


@shared_task(name="integrations.push_conversation_to_zoho", bind=True, max_retries=2)
def push_conversation_to_zoho(self, conversation_id: str, user_id: int = None):
    """Push an analyzed conversation's summary as a Zoho CRM note.

    Uses the rep's own token if connected, falls back to any admin token.
    """
    from apps.conversations.models import Conversation
    from .models import ZohoCredential
    from .services.zoho_sync import push_conversation_note

    try:
        conversation = Conversation.objects.select_related("customer", "created_by").get(id=conversation_id)

        # Prefer the rep's own credential, fall back to admin
        credential = None
        if conversation.created_by_id:
            credential = ZohoCredential.objects.filter(user_id=conversation.created_by_id).first()
        if not credential:
            credential = ZohoCredential.objects.filter(user__role="admin").first()
        if not credential:
            return  # nobody connected to Zoho

        push_conversation_note(conversation, credential)
    except Exception as exc:
        logger.error(f"Zoho note push failed for conversation {conversation_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)


def _pick_credential_for_user(user_id):
    """Rep's own Zoho credential if connected, else any admin credential."""
    from .models import ZohoCredential

    cred = None
    if user_id:
        cred = ZohoCredential.objects.filter(user_id=user_id).first()
    if not cred:
        cred = ZohoCredential.objects.filter(user__role="admin").first()
    return cred


@shared_task(name="integrations.extract_crm_draft", bind=True, max_retries=2)
def extract_crm_draft(self, draft_id: str):
    """Run transcription (if audio) and AI field extraction for a CRMDraft."""
    from .models import CRMDraft
    from .services.crm_extraction import extract_crm_fields
    from .services.zoho_fields import get_schema, module_for_record_type

    try:
        draft = CRMDraft.objects.select_related("attachment", "created_by").get(id=draft_id)
        draft.status = CRMDraft.Status.EXTRACTING
        draft.save(update_fields=["status", "updated_at"])

        # Transcribe audio if attached and raw_text is empty
        if draft.attachment and not draft.raw_text:
            from apps.conversations.services.transcription_service import transcribe_attachment
            transcript = transcribe_attachment(draft.attachment)
            draft.raw_text = transcript
            draft.save(update_fields=["raw_text", "updated_at"])

        if not draft.raw_text:
            draft.status = CRMDraft.Status.FAILED
            draft.error_message = "No text content to extract from."
            draft.save(update_fields=["status", "error_message", "updated_at"])
            return

        credential = _pick_credential_for_user(draft.created_by_id)
        if not credential:
            draft.status = CRMDraft.Status.FAILED
            draft.error_message = "No Zoho connection available for schema fetch."
            draft.save(update_fields=["status", "error_message", "updated_at"])
            return

        module = module_for_record_type(draft.record_type)
        schema = get_schema(credential, module)
        result = extract_crm_fields(draft.raw_text, draft.record_type, schema)

        draft.extracted_fields = result["fields"]
        draft.ai_summary = result["summary"]
        draft.action_items = result["action_items"]
        draft.topics = result["topics"]
        draft.confidence = result["confidence"]
        draft.status = CRMDraft.Status.READY
        draft.error_message = ""
        draft.save()

        logger.info(f"CRMDraft {draft_id} extraction complete: {len(result['fields'])} fields")
    except Exception as exc:
        logger.error(f"CRMDraft extraction failed for {draft_id}: {exc}")
        from .models import CRMDraft as _CRMDraft
        _CRMDraft.objects.filter(id=draft_id).update(
            status=_CRMDraft.Status.FAILED,
            error_message=str(exc)[:500],
        )
        raise self.retry(exc=exc, countdown=30)


@shared_task(name="integrations.submit_crm_draft", bind=True, max_retries=2)
def submit_crm_draft(self, draft_id: str):
    """Create the Lead/Account in Zoho with the draft's fields, attach a note."""
    from .models import CRMDraft
    from .services.zoho_sync import submit_draft_to_zoho

    try:
        draft = CRMDraft.objects.select_related("created_by").get(id=draft_id)
        credential = _pick_credential_for_user(draft.created_by_id)
        if not credential:
            draft.status = CRMDraft.Status.FAILED
            draft.error_message = "No Zoho connection available."
            draft.save(update_fields=["status", "error_message", "updated_at"])
            return

        submit_draft_to_zoho(draft, credential)
    except Exception as exc:
        logger.error(f"CRMDraft submit failed for {draft_id}: {exc}")
        from .models import CRMDraft as _CRMDraft
        _CRMDraft.objects.filter(id=draft_id).update(
            status=_CRMDraft.Status.FAILED,
            error_message=str(exc)[:500],
        )
        raise self.retry(exc=exc, countdown=30)
