import json
import logging
import re
from typing import Optional

import httpx
from django.conf import settings
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a CRM assistant. Analyze this conversation and return ONLY a JSON object with these exact fields. No markdown, no explanation, just raw JSON.

{{
  "summary": "2-3 sentence summary of the conversation",
  "customer_requirements": "what the customer needs or wants",
  "pain_points": "customer's challenges or frustrations",
  "pricing_discussion": "any pricing, budget, or cost topics discussed",
  "next_steps": "agreed follow-up actions",
  "sentiment": "one of: very_negative, negative, neutral, positive, very_positive",
  "sentiment_score": 0.0,
  "action_items": [
    {{"description": "action to take", "due_date": "YYYY-MM-DD or null", "priority": "low|medium|high"}}
  ],
  "topics": ["topic1", "topic2"],
  "competitor_mentions": ["competitor_name"]
}}

Conversation:
{raw_text}"""


class ActionItemExtracted(BaseModel):
    description: str
    due_date: Optional[str] = None
    priority: str = "medium"

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        return v if v in {"low", "medium", "high", "urgent"} else "medium"


def _coerce_str(v) -> str:
    """Accept str or list; join list items into a single string."""
    if isinstance(v, list):
        return "; ".join(str(i) for i in v if i)
    return str(v) if v is not None else ""


class ExtractionResult(BaseModel):
    summary: str = ""
    customer_requirements: str = ""
    pain_points: str = ""
    pricing_discussion: str = ""
    next_steps: str = ""
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    action_items: list[ActionItemExtracted] = []
    topics: list[str] = []
    competitor_mentions: list[str] = []

    @field_validator("summary", "customer_requirements", "pain_points",
                     "pricing_discussion", "next_steps", mode="before")
    @classmethod
    def coerce_text_field(cls, v):
        return _coerce_str(v)

    @field_validator("topics", "competitor_mentions", mode="before")
    @classmethod
    def coerce_list_field(cls, v):
        if isinstance(v, str):
            return [v] if v else []
        return v or []

    @field_validator("sentiment", mode="before")
    @classmethod
    def validate_sentiment(cls, v):
        allowed = {"very_negative", "negative", "neutral", "positive", "very_positive"}
        return v if v in allowed else "neutral"

    @field_validator("sentiment_score", mode="before")
    @classmethod
    def clamp_score(cls, v):
        try:
            return max(-1.0, min(1.0, float(v)))
        except (TypeError, ValueError):
            return 0.0


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()


def _call_openai(raw_text: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a CRM assistant. Always respond with valid JSON only.",
            },
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(raw_text=raw_text),
            },
        ],
        response_format={"type": "json_object"},
        timeout=60,
    )
    return response.choices[0].message.content


def _call_ollama(raw_text: str) -> str:
    prompt = EXTRACTION_PROMPT.replace("{raw_text}", raw_text)
    response = httpx.post(
        f"{settings.OLLAMA_URL}/api/generate",
        json={
            "model": settings.OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["response"]


def extract_structured_data(raw_text: str) -> dict:
    last_error = None
    for attempt in range(3):
        try:
            if settings.LLM_PROVIDER == "openai":
                raw_response = _call_openai(raw_text)
            else:
                raw_response = _call_ollama(raw_text)

            cleaned = _strip_markdown(raw_response)
            data = json.loads(cleaned)
            result = ExtractionResult(**data)
            return result.model_dump()

        except Exception as e:
            last_error = e
            logger.warning(f"LLM extraction attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                continue

    logger.error(f"All LLM extraction attempts failed: {last_error}")
    # Return safe defaults so pipeline can continue
    return ExtractionResult().model_dump()
