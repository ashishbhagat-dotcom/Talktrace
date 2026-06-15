"""Extract structured CRM field values from a conversation transcript.

Reads the live Zoho schema, builds a dynamic prompt with picklist constraints,
calls the LLM, validates the response, and returns the extracted field map
plus a conversation summary, action items, and topics.
"""

import json
import logging
import re

import httpx
from django.conf import settings
from django.utils import timezone

from .zoho_fields import (
    EXTRACTION_FIELDS_ACCOUNT,
    EXTRACTION_FIELDS_LEAD,
    module_for_record_type,
)

logger = logging.getLogger(__name__)


DATE_PHRASE_REGEX = re.compile(
    r"\b("
    r"today|tomorrow|yesterday|"
    r"next\s+(?:week|month|year|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"this\s+(?:week|monday|tuesday|wednesday|thursday|friday|saturday|sunday)|"
    r"by\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|end\s+of\s+(?:week|month))|"
    r"in\s+\d+\s+(?:day|days|week|weeks|month|months)|"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
    r")\b",
    re.IGNORECASE,
)


def _resolve_relative_date(phrase: str, today) -> str | None:
    """Resolve a relative date phrase to YYYY-MM-DD using `today` as the base."""
    import dateparser
    from datetime import datetime, timedelta

    base = datetime(today.year, today.month, today.day)
    settings_dict = {"RELATIVE_BASE": base, "PREFER_DATES_FROM": "future"}

    parsed = dateparser.parse(phrase, settings=settings_dict)
    if parsed:
        return parsed.date().isoformat()

    # Fallback for "next <weekday>" which dateparser leaves as None
    m = re.match(r"^next\s+(\w+)$", phrase.strip(), re.I)
    if m:
        bare = m.group(1)
        parsed = dateparser.parse(bare, settings=settings_dict)
        if parsed:
            return (parsed + timedelta(days=7)).date().isoformat()
    return None


def _fix_action_item_dates(action_items: list, raw_text: str, today) -> list:
    """Replace LLM-generated dates with Python-computed dates when the
    item description (or raw_text) contains a recognizable relative phrase.
    """
    if not action_items:
        return action_items

    fixed = []
    for item in action_items:
        if not isinstance(item, dict):
            fixed.append(item)
            continue
        desc = item.get("description") or ""
        match = DATE_PHRASE_REGEX.search(desc)
        if match:
            resolved = _resolve_relative_date(match.group(0), today)
            if resolved:
                item = {**item, "due_date": resolved}
        fixed.append(item)
    return fixed


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()


def _build_prompt(record_type: str, schema: dict, raw_text: str) -> str:
    """Build a structured-output prompt using the live Zoho schema."""
    target_fields = (
        EXTRACTION_FIELDS_LEAD if record_type == "lead" else EXTRACTION_FIELDS_ACCOUNT
    )

    field_specs = []
    for api in target_fields:
        f = schema.get(api)
        if not f or f.get("read_only"):
            continue
        spec = f"- {api} ({f.get('label')}, {f.get('data_type')})"
        if f.get("required"):
            spec += " [REQUIRED]"
        if f.get("data_type") == "picklist" and f.get("picklist_values"):
            opts = ", ".join(f'"{v}"' for v in f["picklist_values"])
            spec += f" — must be one of: {opts}"
        if f.get("max_length"):
            spec += f" (max {f['max_length']} chars)"
        field_specs.append(spec)

    field_block = "\n".join(field_specs)

    label = "Lead" if record_type == "lead" else "Account"
    today = timezone.localdate()
    today_str = today.isoformat()
    weekday_name = today.strftime("%A")
    return f"""You are a CRM data extraction assistant. Read the conversation below and extract information for creating a Zoho CRM {label}.

TODAY IS {today_str} ({weekday_name}). Use this date to resolve relative date references in the conversation. For example "tomorrow" = the next day after {today_str}, "next Tuesday" = the Tuesday after {today_str}, "by Friday" = the upcoming Friday on or after {today_str}, "next week" = 7 days after {today_str}. Never use a year other than {today.year} (or {today.year + 1} if the date has already passed in {today.year}).

For each field, output the extracted value or null if not mentioned. Do NOT invent or guess values that are not clearly supported by the conversation. For picklist fields, you MUST choose from the listed options exactly, or use null.

Fields to extract:
{field_block}

Also produce:
- summary: 2-3 sentence summary of the conversation
- action_items: list of follow-up actions, each {{description, due_date (YYYY-MM-DD or null), priority (low|medium|high)}}
- topics: list of short topic tags
- confidence: dict mapping each field api_name to a confidence score 0.0-1.0

Return ONLY a JSON object with this exact shape (no markdown, no commentary):
{{
  "fields": {{ <api_name>: <value or null>, ... }},
  "summary": "...",
  "action_items": [...],
  "topics": [...],
  "confidence": {{ <api_name>: 0.0, ... }}
}}

Conversation:
{raw_text}"""


def _call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a CRM data extraction assistant. Always respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        timeout=90,
    )
    return response.choices[0].message.content


def _call_ollama(prompt: str) -> str:
    response = httpx.post(
        f"{settings.OLLAMA_URL}/api/generate",
        json={
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["response"]


def _coerce_value(value, field_spec: dict):
    """Clean and constrain a single field value based on its Zoho spec."""
    if value is None or value == "":
        return None

    data_type = field_spec.get("data_type", "text")

    if data_type == "picklist":
        allowed = field_spec.get("picklist_values", [])
        if value in allowed:
            return value
        # Try case-insensitive match
        lower = str(value).lower()
        for v in allowed:
            if v.lower() == lower:
                return v
        return None  # invalid picklist value → drop

    if data_type in ("text", "textarea", "email", "phone", "website"):
        s = str(value).strip()
        max_len = field_spec.get("max_length")
        if max_len and len(s) > max_len:
            s = s[:max_len]
        return s or None

    if data_type in ("integer", "bigint"):
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    if data_type in ("double", "currency"):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    if data_type == "boolean":
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"true", "yes", "1"}

    return str(value).strip() or None


def extract_crm_fields(raw_text: str, record_type: str, schema: dict) -> dict:
    """Extract CRM fields from a conversation transcript.

    Returns:
        {
          "fields": {api_name: value, ...},   # null values dropped
          "summary": str,
          "action_items": [{description, due_date, priority}, ...],
          "topics": [str, ...],
          "confidence": {api_name: float, ...},
        }
    """
    prompt = _build_prompt(record_type, schema, raw_text)

    last_error = None
    for attempt in range(3):
        try:
            if settings.LLM_PROVIDER == "openai":
                raw_response = _call_openai(prompt)
            else:
                raw_response = _call_ollama(prompt)

            data = json.loads(_strip_markdown(raw_response))

            fields_in = data.get("fields", {}) or {}
            cleaned_fields = {}
            for api, val in fields_in.items():
                spec = schema.get(api)
                if not spec:
                    continue
                coerced = _coerce_value(val, spec)
                if coerced is not None:
                    cleaned_fields[api] = coerced

            confidence_in = data.get("confidence", {}) or {}
            confidence = {k: float(v) for k, v in confidence_in.items() if k in cleaned_fields}

            today = timezone.localdate()
            action_items = _fix_action_item_dates(
                data.get("action_items", []) or [], raw_text, today,
            )

            return {
                "fields": cleaned_fields,
                "summary": str(data.get("summary", "") or "")[:5000],
                "action_items": action_items,
                "topics": data.get("topics", []) or [],
                "confidence": confidence,
            }
        except Exception as e:
            last_error = e
            logger.warning(f"CRM extraction attempt {attempt + 1} failed: {e}")
            continue

    logger.error(f"All CRM extraction attempts failed: {last_error}")
    return {
        "fields": {},
        "summary": "",
        "action_items": [],
        "topics": [],
        "confidence": {},
    }
