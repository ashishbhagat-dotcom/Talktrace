import logging
from datetime import datetime

from django.utils import timezone

from apps.customers.models import Customer
from . import zoho_client as zc

logger = logging.getLogger(__name__)


def _map_zoho_record_to_customer(record: dict, customer_type: str) -> dict:
    """Extract Customer fields from a Zoho Contact or Lead record."""
    if customer_type == "contact":
        first = record.get("First_Name", "") or ""
        last = record.get("Last_Name", "") or ""
        name = f"{first} {last}".strip() or record.get("Full_Name", "") or "Unknown"
        company = record.get("Account_Name", {})
        if isinstance(company, dict):
            company = company.get("name", "")
    else:
        first = record.get("First_Name", "") or ""
        last = record.get("Last_Name", "") or ""
        name = f"{first} {last}".strip() or "Unknown"
        company = record.get("Company", "") or ""

    return {
        "name": name[:255],
        "email": (record.get("Email") or "")[:255],
        "phone": (record.get("Phone") or record.get("Mobile") or "")[:50],
        "company": str(company)[:255],
        "type": customer_type,
    }


def sync_from_zoho(credential) -> dict:
    """Pull Contacts and Leads from Zoho, upsert into Customer table."""
    access_token = zc.get_valid_token(credential)

    # Use last sync time for incremental pulls (RFC 1123 format Zoho expects)
    modified_since = None
    if credential.last_sync_at:
        modified_since = credential.last_sync_at.strftime("%a, %d %b %Y %H:%M:%S GMT")

    counts = {"created": 0, "updated": 0, "errors": 0}

    for module, customer_type in [("Contacts", "contact"), ("Leads", "lead")]:
        page = 1
        while True:
            try:
                result = zc.fetch_records(access_token, module, modified_since, page)
            except Exception as e:
                logger.error(f"Failed to fetch Zoho {module} page {page}: {e}")
                counts["errors"] += 1
                break

            records = result.get("data", [])
            if not records:
                break

            for record in records:
                zoho_id = record.get("id")
                if not zoho_id:
                    continue
                try:
                    fields = _map_zoho_record_to_customer(record, customer_type)
                    obj, created = Customer.objects.update_or_create(
                        zoho_record_id=zoho_id,
                        defaults=fields,
                    )
                    if created:
                        counts["created"] += 1
                    else:
                        counts["updated"] += 1
                except Exception as e:
                    logger.error(f"Failed to upsert Zoho record {zoho_id}: {e}")
                    counts["errors"] += 1

            more = result.get("info", {}).get("more_records", False)
            if not more:
                break
            page += 1

    credential.last_sync_at = timezone.now()
    credential.save(update_fields=["last_sync_at", "updated_at"])

    logger.info(f"Zoho sync done for user {credential.user_id}: {counts}")
    return counts


_PRIORITY_MAP = {
    "low": "Low",
    "medium": "Normal",
    "high": "High",
    "urgent": "Highest",
}

_MODULE_MAP = {"contact": "Contacts", "lead": "Leads", "account": "Accounts"}


def push_action_item_task(action_item, credential) -> str | None:
    """Push an ActionItem as a Task on the linked Zoho CRM record. Returns Zoho task ID."""
    customer = action_item.conversation.customer
    if not customer.zoho_record_id:
        logger.debug(f"Customer {customer.id} has no Zoho record ID, skipping task push")
        return None

    try:
        access_token = zc.get_valid_token(credential)
        zoho_module = _MODULE_MAP.get(customer.type, "Contacts")

        rep_name = (
            action_item.conversation.created_by.name
            if action_item.conversation.created_by
            else "Unknown Rep"
        )
        subject = f"[Talktrace] {action_item.description[:200]}"
        description = (
            f"Follow-up from Talktrace conversation on "
            f"{action_item.conversation.interaction_date.strftime('%b %d, %Y')} "
            f"with {rep_name}.\n\nTask: {action_item.description}"
        )
        due_date = action_item.due_date.strftime("%Y-%m-%d") if action_item.due_date else None
        priority = _PRIORITY_MAP.get(action_item.priority, "Normal")

        task_id = zc.create_task(
            access_token,
            subject=subject,
            description=description,
            due_date=due_date,
            priority=priority,
            zoho_record_id=customer.zoho_record_id,
            zoho_module=zoho_module,
        )
        logger.info(f"Created Zoho task {task_id} for action item {action_item.id}")
        return task_id

    except Exception as e:
        logger.error(f"Failed to push action item {action_item.id} to Zoho: {e}")
        raise


def submit_draft_to_zoho(draft, credential):
    """Create Zoho Lead/Account from a CRMDraft and attach a note with the transcript."""
    from apps.customers.models import Customer
    from .zoho_fields import get_schema, module_for_record_type, required_fields

    module = module_for_record_type(draft.record_type)
    schema = get_schema(credential, module)

    # Defense-in-depth: validate required fields are present
    missing = [
        api for api in required_fields(schema)
        if not draft.extracted_fields.get(api)
    ]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    access_token = zc.get_valid_token(credential)

    # Create the Zoho record
    record_id = zc.create_record(access_token, module, draft.extracted_fields)
    draft.zoho_record_id = record_id

    # Build the note body
    rep_name = draft.created_by.name if draft.created_by else "Unknown Rep"
    rep_email = draft.created_by.email if draft.created_by else ""
    record_label = "Lead" if draft.record_type == "lead" else "Account"
    title = f"Talktrace: {record_label} created from conversation by {rep_name} — {timezone.now().strftime('%b %d, %Y')}"

    lines = [f"Created by: {rep_name} ({rep_email})" if rep_email else f"Created by: {rep_name}"]
    if draft.ai_summary:
        lines.append(f"\n**Summary:** {draft.ai_summary}")
    if draft.topics:
        lines.append(f"\n**Topics:** {', '.join(draft.topics)}")
    if draft.action_items:
        lines.append("\n**Action Items:**")
        for item in draft.action_items:
            desc = item.get("description") if isinstance(item, dict) else str(item)
            if desc:
                due = item.get("due_date") if isinstance(item, dict) else None
                lines.append(f"  • {desc}" + (f" (due {due})" if due else ""))

    note_id = zc.create_note(access_token, module, record_id, title, "\n".join(lines))
    draft.zoho_note_id = note_id

    # Mirror as a local Customer + Conversation so this draft appears in dashboards
    customer = None
    try:
        customer_type = "lead" if draft.record_type == "lead" else "account"
        name = (
            draft.extracted_fields.get("Account_Name")
            or " ".join(filter(None, [
                draft.extracted_fields.get("First_Name"),
                draft.extracted_fields.get("Last_Name"),
            ])).strip()
            or "Unknown"
        )
        customer, _ = Customer.objects.update_or_create(
            zoho_record_id=record_id,
            defaults={
                "name": name[:255],
                "email": (draft.extracted_fields.get("Email") or draft.extracted_fields.get("Email_ID") or "")[:255],
                "phone": (draft.extracted_fields.get("Phone") or draft.extracted_fields.get("Mobile") or "")[:50],
                "company": (draft.extracted_fields.get("Company") or draft.extracted_fields.get("Account_Name") or "")[:255],
                "type": customer_type,
            },
        )
    except Exception as e:
        logger.warning(f"Failed to mirror draft {draft.id} as local Customer: {e}")

    # Mirror as a local Conversation so it shows up in dashboards and conversation list
    if customer:
        try:
            from apps.conversations.models import ActionItem, Conversation
            conversation = Conversation.objects.create(
                customer=customer,
                conversation_type="other",
                raw_text=draft.raw_text,
                ai_summary=draft.ai_summary,
                topics=draft.topics or [],
                created_by=draft.created_by,
                ai_status=Conversation.AIStatus.COMPLETED,
                interaction_date=draft.created_at,
            )
            # Mirror action items locally so they show up in the Action Items page
            for item in (draft.action_items or []):
                if not isinstance(item, dict) or not item.get("description"):
                    continue
                ActionItem.objects.create(
                    conversation=conversation,
                    description=item["description"][:500],
                    due_date=item.get("due_date") or None,
                    priority=item.get("priority", "medium"),
                )
        except Exception as e:
            logger.warning(f"Failed to mirror draft {draft.id} as local Conversation: {e}")

    # Push each action item as a Zoho Task linked to the new record
    for item in (draft.action_items or []):
        if not isinstance(item, dict) or not item.get("description"):
            continue
        try:
            zc.create_task(
                access_token,
                subject=item["description"][:250],
                description="From Talktrace draft conversation.",
                due_date=item.get("due_date") or None,
                priority={"high": "High", "low": "Low"}.get(item.get("priority"), "Normal"),
                zoho_record_id=record_id,
                zoho_module=module,
            )
        except Exception as e:
            logger.warning(f"Failed to push action item to Zoho for draft {draft.id}: {e}")

    # Finalize draft
    from ..models import CRMDraft
    draft.status = CRMDraft.Status.SUBMITTED
    draft.submitted_at = timezone.now()
    draft.error_message = ""
    draft.save(update_fields=[
        "status", "zoho_record_id", "zoho_note_id", "submitted_at",
        "error_message", "updated_at",
    ])
    logger.info(f"CRMDraft {draft.id} submitted as Zoho {module} {record_id}")


def push_conversation_note(conversation, credential) -> bool:
    """Push AI summary as a Note on the linked Zoho CRM record."""
    customer = conversation.customer
    if not customer.zoho_record_id:
        logger.debug(f"Customer {customer.id} has no Zoho record ID, skipping note push")
        return False

    if not conversation.ai_summary:
        return False

    try:
        access_token = zc.get_valid_token(credential)

        # Determine Zoho module from customer type
        module_map = {"contact": "Contacts", "lead": "Leads", "account": "Accounts"}
        module = module_map.get(customer.type, "Contacts")

        rep_name = conversation.created_by.name if conversation.created_by else "Unknown Rep"
        rep_email = conversation.created_by.email if conversation.created_by else ""

        title = f"Talktrace: {conversation.get_conversation_type_display()} by {rep_name} — {conversation.interaction_date.strftime('%b %d, %Y')}"

        lines = [f"Rep: {rep_name} ({rep_email})" if rep_email else f"Rep: {rep_name}"]
        lines.append(f"\n**Summary:** {conversation.ai_summary}")
        if conversation.customer_requirements:
            lines.append(f"\n**Customer Requirements:** {conversation.customer_requirements}")
        if conversation.pain_points:
            lines.append(f"\n**Pain Points:** {conversation.pain_points}")
        if conversation.next_steps:
            lines.append(f"\n**Next Steps:** {conversation.next_steps}")
        if conversation.sentiment:
            lines.append(f"\n**Sentiment:** {conversation.sentiment.replace('_', ' ').title()}")

        content = "\n".join(lines)

        note_id = zc.create_note(access_token, module, customer.zoho_record_id, title, content)
        logger.info(f"Created Zoho note {note_id} for conversation {conversation.id}")
        return True

    except Exception as e:
        logger.error(f"Failed to push conversation {conversation.id} to Zoho: {e}")
        return False
