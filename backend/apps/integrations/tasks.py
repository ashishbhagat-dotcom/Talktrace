import logging

from celery import shared_task

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


@shared_task(name="integrations.push_conversation_to_zoho", bind=True, max_retries=2)
def push_conversation_to_zoho(self, conversation_id: str, user_id: int):
    """Push an analyzed conversation's summary as a Zoho CRM note."""
    from apps.conversations.models import Conversation
    from .models import ZohoCredential
    from .services.zoho_sync import push_conversation_note

    try:
        credential = ZohoCredential.objects.get(user_id=user_id)
        conversation = Conversation.objects.select_related("customer").get(id=conversation_id)
        push_conversation_note(conversation, credential)
    except ZohoCredential.DoesNotExist:
        pass  # user not connected to Zoho
    except Exception as exc:
        logger.error(f"Zoho note push failed for conversation {conversation_id}: {exc}")
        raise self.retry(exc=exc, countdown=30)
