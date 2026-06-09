import logging
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

ZOHO_ACCOUNTS_URL = getattr(settings, "ZOHO_ACCOUNTS_URL", "https://accounts.zoho.com")
ZOHO_API_URL = getattr(settings, "ZOHO_API_URL", "https://www.zohoapis.com")
SCOPES = "ZohoCRM.modules.Contacts.READ,ZohoCRM.modules.Leads.READ,ZohoCRM.modules.Notes.CREATE,ZohoCRM.modules.Tasks.CREATE,ZohoCRM.users.READ"


def get_auth_url(redirect_uri: str, state: str = "") -> str:
    params = {
        "client_id": settings.ZOHO_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "state": state,
        "prompt": "consent",
    }
    return f"{ZOHO_ACCOUNTS_URL}/oauth/v2/auth?{urlencode(params)}"


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange auth code for access + refresh tokens."""
    response = httpx.post(
        f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token",
        data={
            "client_id": settings.ZOHO_CLIENT_ID,
            "client_secret": settings.ZOHO_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code": code,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise ValueError(f"Zoho token exchange error: {data['error']}")
    expires_in = int(data.get("expires_in", 3600))
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "expires_at": timezone.now() + timedelta(seconds=expires_in - 60),
    }


def refresh_access_token(refresh_token: str) -> dict:
    """Get a new access token using the refresh token."""
    response = httpx.post(
        f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token",
        data={
            "client_id": settings.ZOHO_CLIENT_ID,
            "client_secret": settings.ZOHO_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise ValueError(f"Zoho token refresh error: {data['error']}")
    expires_in = int(data.get("expires_in", 3600))
    return {
        "access_token": data["access_token"],
        "expires_at": timezone.now() + timedelta(seconds=expires_in - 60),
    }


def get_valid_token(credential) -> str:
    """Return a valid access token, refreshing if expired."""
    if credential.is_token_expired:
        logger.info(f"Refreshing Zoho token for user {credential.user_id}")
        token_data = refresh_access_token(credential.refresh_token)
        credential.access_token = token_data["access_token"]
        credential.expires_at = token_data["expires_at"]
        credential.save(update_fields=["access_token", "expires_at", "updated_at"])
    return credential.access_token


def _headers(access_token: str) -> dict:
    return {"Authorization": f"Zoho-oauthtoken {access_token}"}


def get_current_user(access_token: str) -> dict:
    response = httpx.get(
        f"{ZOHO_API_URL}/crm/v2/users?type=CurrentUser",
        headers=_headers(access_token),
        timeout=30,
    )
    response.raise_for_status()
    users = response.json().get("users", [])
    return users[0] if users else {}


def fetch_records(access_token: str, module: str, modified_since: str = None, page: int = 1) -> dict:
    """Fetch a page of CRM records. Returns {data: [...], info: {...}}."""
    headers = _headers(access_token)
    if modified_since:
        headers["If-Modified-Since"] = modified_since
    params = {"page": page, "per_page": 200}
    response = httpx.get(
        f"{ZOHO_API_URL}/crm/v2/{module}",
        headers=headers,
        params=params,
        timeout=30,
    )
    if response.status_code == 304:
        return {"data": [], "info": {"more_records": False}}
    response.raise_for_status()
    return response.json()


def create_task(
    access_token: str,
    subject: str,
    description: str = "",
    due_date: str = None,
    priority: str = "Normal",
    zoho_record_id: str = None,
    zoho_module: str = None,
) -> str:
    """Create a Task in Zoho CRM. Returns the new task ID."""
    task_data: dict = {
        "Subject": subject[:255],
        "Status": "Not Started",
        "Priority": priority,
    }
    if description:
        task_data["Description"] = description[:32000]
    if due_date:
        task_data["Due_Date"] = due_date  # YYYY-MM-DD
    if zoho_record_id and zoho_module:
        task_data["Who_Id"] = {"id": zoho_record_id, "module": {"api_name": zoho_module}}

    response = httpx.post(
        f"{ZOHO_API_URL}/crm/v2/Tasks",
        headers=_headers(access_token),
        json={"data": [task_data]},
        timeout=30,
    )
    response.raise_for_status()
    result = response.json().get("data", [{}])[0]
    if result.get("status") != "success":
        raise ValueError(f"Zoho task creation failed: {result}")
    return result["details"]["id"]


def create_note(access_token: str, module: str, record_id: str, title: str, content: str) -> str:
    """Create a Note on a Zoho CRM record. Returns the new note ID."""
    payload = {
        "data": [{
            "Note_Title": title[:250],
            "Note_Content": content[:32000],
            "Parent_Id": record_id,
            "se_module": module,
        }]
    }
    response = httpx.post(
        f"{ZOHO_API_URL}/crm/v2/Notes",
        headers=_headers(access_token),
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    result = response.json().get("data", [{}])[0]
    if result.get("status") != "success":
        raise ValueError(f"Zoho note creation failed: {result}")
    return result["details"]["id"]
