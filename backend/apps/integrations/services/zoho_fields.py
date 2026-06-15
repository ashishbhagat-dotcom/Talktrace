"""Fetch and cache Zoho field schemas (with layout-level required flags).

The Zoho fields metadata API returns fields for a module but only marks
`system_mandatory`. Layout metadata reveals which fields are required by
the org's CRM layout. We union both into a single schema per module.
"""

import logging
from datetime import timedelta

import httpx
from django.conf import settings
from django.utils import timezone

from . import zoho_client as zc

logger = logging.getLogger(__name__)

SCHEMA_CACHE_TTL = timedelta(hours=24)

# Fields the AI extractor should always try to populate (superset of required).
# Final required-set comes from the live layout schema; this is the broader
# list we surface to the LLM and to the rep in the review screen.
EXTRACTION_FIELDS_LEAD = [
    "First_Name", "Last_Name", "Email", "Phone", "Mobile",
    "Company", "Designation", "Website", "Country", "Description",
    "Lead_Source", "Lead_Status", "Salutation",
]

EXTRACTION_FIELDS_ACCOUNT = [
    "Account_Name", "Email_ID", "Phone", "Website",
    "Industry", "Employees", "Description",
    "Account_Type", "Business", "Opportunity_1",
    "Customer_Type", "Priority_Account",
    "Revenue_Range_Monthly", "Revenue_at_Risk",
    "CRN", "LinkedIn_URL",
    "Billing_Street", "Billing_State", "Billing_Code", "Billing_Country",
]


def _api_url() -> str:
    return getattr(settings, "ZOHO_API_URL", "https://www.zohoapis.com")


def _fetch_layout_required(token: str, module: str) -> set[str]:
    """Return api_names of fields marked required in the standard layout."""
    r = httpx.get(
        f"{_api_url()}/crm/v2/settings/layouts",
        params={"module": module},
        headers={"Authorization": f"Zoho-oauthtoken {token}"},
        timeout=30,
    )
    r.raise_for_status()
    required = set()
    for layout in r.json().get("layouts", []):
        for section in layout.get("sections", []):
            for f in section.get("fields", []):
                if f.get("required") or f.get("system_mandatory"):
                    api = f.get("api_name")
                    if api:
                        required.add(api)
    return required


def _fetch_fields(token: str, module: str) -> list[dict]:
    r = httpx.get(
        f"{_api_url()}/crm/v2/settings/fields",
        params={"module": module},
        headers={"Authorization": f"Zoho-oauthtoken {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("fields", [])


def _normalize_field(f: dict, layout_required: set[str]) -> dict:
    """Convert a Zoho field record into our schema shape."""
    api = f["api_name"]
    out = {
        "api_name": api,
        "label": f.get("field_label", api),
        "data_type": f.get("data_type", "text"),
        "system_mandatory": bool(f.get("system_mandatory")),
        "required": bool(f.get("system_mandatory") or api in layout_required),
        "read_only": bool(f.get("read_only") or f.get("field_read_only")),
        "max_length": f.get("length"),
    }
    if f.get("data_type") == "picklist":
        out["picklist_values"] = [
            p["actual_value"]
            for p in f.get("pick_list_values", [])
            if p.get("actual_value") and p["actual_value"] != "-None-"
        ]
    return out


def fetch_schema_for_module(token: str, module: str) -> dict:
    """Fetch the full field schema for a Zoho module.

    Returns dict keyed by api_name. Each entry includes `required` flag that
    is true if either system-mandatory OR marked required in any layout.
    """
    layout_required = _fetch_layout_required(token, module)
    fields = _fetch_fields(token, module)
    schema = {}
    for f in fields:
        if not f.get("api_name"):
            continue
        schema[f["api_name"]] = _normalize_field(f, layout_required)
    return schema


def get_schema(credential, module: str, force_refresh: bool = False) -> dict:
    """Return cached schema for module, refreshing if stale or missing.

    `module` is one of "Leads", "Accounts" (Zoho API names).
    """
    cache = credential.field_schema_cache or {}
    fetched_at = credential.field_schema_fetched_at
    stale = (
        not fetched_at
        or (timezone.now() - fetched_at) > SCHEMA_CACHE_TTL
    )

    if not force_refresh and module in cache and not stale:
        return cache[module]

    token = zc.get_valid_token(credential)
    schema = fetch_schema_for_module(token, module)
    cache[module] = schema
    credential.field_schema_cache = cache
    credential.field_schema_fetched_at = timezone.now()
    credential.save(update_fields=[
        "field_schema_cache", "field_schema_fetched_at", "updated_at"
    ])
    return schema


def required_fields(schema: dict) -> list[str]:
    """Return api_names that are required (system_mandatory or layout-required)."""
    return [api for api, f in schema.items() if f.get("required") and not f.get("read_only")]


def extraction_fields(record_type: str) -> list[str]:
    """Return the api_name list the AI should try to extract for a record type."""
    if record_type == "lead":
        return EXTRACTION_FIELDS_LEAD
    if record_type == "account":
        return EXTRACTION_FIELDS_ACCOUNT
    raise ValueError(f"Unknown record_type: {record_type}")


def module_for_record_type(record_type: str) -> str:
    return {"lead": "Leads", "account": "Accounts"}[record_type]
