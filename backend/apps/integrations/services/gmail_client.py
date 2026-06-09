import base64
import logging
from datetime import timedelta
from email import message_from_bytes
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

GOOGLE_ACCOUNTS_URL = "https://accounts.google.com"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_URL = "https://gmail.googleapis.com/gmail/v1"
SCOPES = "https://www.googleapis.com/auth/gmail.readonly"


def get_auth_url(redirect_uri: str, state: str = "") -> str:
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "state": state,
        "prompt": "consent",
    }
    return f"{GOOGLE_ACCOUNTS_URL}/o/oauth2/v2/auth?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code": code,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise ValueError(f"Google token exchange error: {data['error']}")
    expires_in = int(data.get("expires_in", 3600))
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token", ""),
        "expires_at": timezone.now() + timedelta(seconds=expires_in - 60),
    }


def refresh_access_token(refresh_token: str) -> dict:
    response = httpx.post(
        GOOGLE_TOKEN_URL,
        data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise ValueError(f"Google token refresh error: {data['error']}")
    expires_in = int(data.get("expires_in", 3600))
    return {
        "access_token": data["access_token"],
        "expires_at": timezone.now() + timedelta(seconds=expires_in - 60),
    }


def get_valid_token(credential) -> str:
    if credential.is_token_expired:
        token_data = refresh_access_token(credential.refresh_token)
        credential.access_token = token_data["access_token"]
        credential.expires_at = token_data["expires_at"]
        credential.save(update_fields=["access_token", "expires_at", "updated_at"])
    return credential.access_token


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


def get_user_email(access_token: str) -> str:
    response = httpx.get(
        f"{GMAIL_API_URL}/users/me/profile",
        headers=_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("emailAddress", "")


def list_threads(access_token: str, query: str = "", max_results: int = 20) -> list:
    """Search Gmail threads. Returns list of {id, snippet}."""
    params = {"maxResults": max_results, "q": query}
    response = httpx.get(
        f"{GMAIL_API_URL}/users/me/threads",
        headers=_headers(access_token),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json().get("threads", [])


def get_thread(access_token: str, thread_id: str) -> dict:
    """Fetch a full thread and return {subject, date, raw_text, message_count}."""
    response = httpx.get(
        f"{GMAIL_API_URL}/users/me/threads/{thread_id}",
        headers=_headers(access_token),
        params={"format": "full"},
        timeout=30,
    )
    response.raise_for_status()
    thread = response.json()
    return _parse_thread(thread)


def _decode_body(data: str) -> str:
    if not data:
        return ""
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _extract_text_from_parts(parts: list) -> str:
    """Recursively extract text/plain from MIME parts."""
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            body_data = part.get("body", {}).get("data", "")
            text = _decode_body(body_data)
            if text.strip():
                return text
        if "parts" in part:
            result = _extract_text_from_parts(part["parts"])
            if result:
                return result
    # fallback: try text/html if no plain found
    for part in parts:
        mime = part.get("mimeType", "")
        if mime == "text/html":
            import re
            body_data = part.get("body", {}).get("data", "")
            html = _decode_body(body_data)
            return re.sub(r"<[^>]+>", " ", html).strip()
        if "parts" in part:
            result = _extract_text_from_parts(part["parts"])
            if result:
                return result
    return ""


def _get_header(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _parse_thread(thread: dict) -> dict:
    messages = thread.get("messages", [])
    subject = ""
    parts_text = []
    latest_date = ""

    for i, msg in enumerate(messages):
        headers = msg.get("payload", {}).get("headers", [])
        if i == 0:
            subject = _get_header(headers, "Subject")
        sender = _get_header(headers, "From")
        date_str = _get_header(headers, "Date")
        if date_str:
            latest_date = date_str

        payload = msg.get("payload", {})
        if "parts" in payload:
            body = _extract_text_from_parts(payload["parts"])
        else:
            body = _decode_body(payload.get("body", {}).get("data", ""))

        body = body.strip()
        if body:
            parts_text.append(f"--- Email {i+1} ---\nFrom: {sender}\nDate: {date_str}\n\n{body}")

    raw_text = f"Subject: {subject}\n\n" + "\n\n".join(parts_text)
    return {
        "id": thread.get("id"),
        "subject": subject,
        "date": latest_date,
        "raw_text": raw_text,
        "message_count": len(messages),
    }
