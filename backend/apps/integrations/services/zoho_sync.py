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
