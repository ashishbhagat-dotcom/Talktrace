import logging

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.response import Response

from .models import ZohoCredential, GmailCredential
from .services import zoho_client as zc

logger = logging.getLogger(__name__)

FRONTEND_URL = getattr(settings, "FRONTEND_URL", "http://localhost:5173")
ZOHO_REDIRECT_URI = getattr(settings, "ZOHO_REDIRECT_URI", "http://localhost:8001/api/integrations/zoho/callback/")


def _redirect_uri(request):
    return ZOHO_REDIRECT_URI


def _get_org_credential():
    """Return the single org-wide Zoho credential (stored on an admin user)."""
    return ZohoCredential.objects.select_related("user").filter(
        user__role="admin"
    ).first()


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def zoho_status(request):
    try:
        cred = ZohoCredential.objects.get(user=request.user)
        return Response({
            "connected": True,
            "zoho_user_email": cred.zoho_user_email,
            "last_sync_at": cred.last_sync_at,
        })
    except ZohoCredential.DoesNotExist:
        return Response({"connected": False})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def zoho_connect(request):
    if not getattr(settings, "ZOHO_CLIENT_ID", None):
        return Response(
            {"error": "Zoho integration is not configured. Set ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    auth_url = zc.get_auth_url(
        redirect_uri=_redirect_uri(request),
        state=str(request.user.id),
    )
    return Response({"auth_url": auth_url})


def zoho_callback(request):
    """OAuth callback — exchanges code, saves credential, redirects to frontend."""
    error = request.GET.get("error")
    if error:
        logger.warning(f"Zoho OAuth error: {error}")
        return HttpResponseRedirect(f"{FRONTEND_URL}/settings?zoho=error&reason={error}")

    code = request.GET.get("code")
    state = request.GET.get("state")  # user ID we passed in state

    if not code:
        return HttpResponseRedirect(f"{FRONTEND_URL}/settings?zoho=error&reason=no_code")

    try:
        token_data = zc.exchange_code(code, redirect_uri=ZOHO_REDIRECT_URI)

        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=state)
        except (User.DoesNotExist, ValueError):
            return HttpResponseRedirect(f"{FRONTEND_URL}/settings?zoho=error&reason=invalid_state")

        zoho_user_email = ""
        zoho_org_id = ""
        try:
            zoho_user = zc.get_current_user(token_data["access_token"])
            zoho_user_email = zoho_user.get("email", "")
            zoho_org_id = str(zoho_user.get("org", {}).get("id", "") if isinstance(zoho_user.get("org"), dict) else "")
        except Exception as e:
            logger.warning(f"Could not fetch Zoho user info: {e}")

        ZohoCredential.objects.update_or_create(
            user=user,
            defaults={
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                "expires_at": token_data["expires_at"],
                "zoho_user_email": zoho_user_email,
                "zoho_org_id": zoho_org_id,
            },
        )

        from .tasks import sync_zoho_for_user
        sync_zoho_for_user.delay(str(user.id))

        return HttpResponseRedirect(f"{FRONTEND_URL}/settings?zoho=connected")

    except Exception as e:
        logger.error(f"Zoho callback failed: {e}")
        return HttpResponseRedirect(f"{FRONTEND_URL}/settings?zoho=error&reason=token_exchange_failed")


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def zoho_disconnect(request):
    ZohoCredential.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def zoho_sync_now(request):
    try:
        ZohoCredential.objects.get(user=request.user)
    except ZohoCredential.DoesNotExist:
        return Response({"error": "Not connected to Zoho"}, status=status.HTTP_400_BAD_REQUEST)

    from .tasks import sync_zoho_for_user
    sync_zoho_for_user.delay(str(request.user.id))
    return Response({"status": "sync started"})


# ─── Gmail Integration Views ──────────────────────────────────────────────────

GMAIL_REDIRECT_URI = getattr(settings, "GMAIL_REDIRECT_URI", "http://localhost:8001/api/integrations/gmail/callback/")


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def gmail_status(request):
    try:
        cred = GmailCredential.objects.get(user=request.user)
        return Response({"connected": True, "gmail_email": cred.gmail_email})
    except GmailCredential.DoesNotExist:
        return Response({"connected": False})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def gmail_connect(request):
    if not getattr(settings, "GOOGLE_CLIENT_ID", None):
        return Response(
            {"error": "Gmail integration is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    from .services import gmail_client as gc
    auth_url = gc.get_auth_url(redirect_uri=GMAIL_REDIRECT_URI, state=str(request.user.id))
    return Response({"auth_url": auth_url})


def gmail_callback(request):
    from .services import gmail_client as gc
    error = request.GET.get("error")
    if error:
        return HttpResponseRedirect(f"{FRONTEND_URL}/settings?gmail=error&reason={error}")

    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code:
        return HttpResponseRedirect(f"{FRONTEND_URL}/settings?gmail=error&reason=no_code")

    try:
        token_data = gc.exchange_code(code, redirect_uri=GMAIL_REDIRECT_URI)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            user = User.objects.get(id=state)
        except (User.DoesNotExist, ValueError):
            return HttpResponseRedirect(f"{FRONTEND_URL}/settings?gmail=error&reason=invalid_state")

        gmail_email = ""
        try:
            gmail_email = gc.get_user_email(token_data["access_token"])
        except Exception as e:
            logger.warning(f"Could not fetch Gmail user email: {e}")

        GmailCredential.objects.update_or_create(
            user=user,
            defaults={
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                "expires_at": token_data["expires_at"],
                "gmail_email": gmail_email,
            },
        )
        return HttpResponseRedirect(f"{FRONTEND_URL}/settings?gmail=connected")
    except Exception as e:
        logger.error(f"Gmail callback failed: {e}")
        return HttpResponseRedirect(f"{FRONTEND_URL}/settings?gmail=error&reason=token_exchange_failed")


@api_view(["DELETE"])
@permission_classes([permissions.IsAuthenticated])
def gmail_disconnect(request):
    GmailCredential.objects.filter(user=request.user).delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def gmail_threads(request):
    """Search Gmail threads. Query param: q (search string), customer_email."""
    try:
        cred = GmailCredential.objects.get(user=request.user)
    except GmailCredential.DoesNotExist:
        return Response({"error": "Gmail not connected"}, status=status.HTTP_400_BAD_REQUEST)

    from .services import gmail_client as gc
    query = request.GET.get("q", "")
    customer_email = request.GET.get("customer_email", "")
    # Use customer_email as default filter only when no explicit search query is given
    if customer_email and not query:
        query = f"from:{customer_email} OR to:{customer_email}"

    try:
        access_token = gc.get_valid_token(cred)
        threads = gc.list_threads(access_token, query=query, max_results=15)
        return Response({"threads": threads})
    except Exception as e:
        logger.error(f"Gmail thread list failed for user {request.user.id}: {e}")
        return Response({"error": "Failed to fetch threads"}, status=status.HTTP_502_BAD_GATEWAY)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def gmail_thread_detail(request, thread_id):
    """Fetch and parse a single Gmail thread."""
    try:
        cred = GmailCredential.objects.get(user=request.user)
    except GmailCredential.DoesNotExist:
        return Response({"error": "Gmail not connected"}, status=status.HTTP_400_BAD_REQUEST)

    from .services import gmail_client as gc
    try:
        access_token = gc.get_valid_token(cred)
        thread = gc.get_thread(access_token, thread_id)
        return Response(thread)
    except Exception as e:
        logger.error(f"Gmail thread fetch failed for thread {thread_id}: {e}")
        return Response({"error": "Failed to fetch thread"}, status=status.HTTP_502_BAD_GATEWAY)


# ─── CRM Draft (Lead/Account from Conversation) ──────────────────────────────

from rest_framework.parsers import FormParser, JSONParser, MultiPartParser  # noqa: E402


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([JSONParser, MultiPartParser, FormParser])
def crm_drafts(request):
    from apps.conversations.models import Attachment
    from .models import CRMDraft
    from .serializers import CRMDraftCreateSerializer, CRMDraftSerializer
    from .tasks import transcribe_crm_draft

    if request.method == "GET":
        qs = CRMDraft.objects.filter(created_by=request.user).order_by("-created_at")
        if request.user.role == "admin":
            qs = CRMDraft.objects.all().order_by("-created_at")
        return Response(CRMDraftSerializer(qs[:50], many=True).data)

    # Handle audio upload (multipart) — create an Attachment first
    attachment_id = None
    audio_file = request.FILES.get("audio") if request.FILES else None
    if audio_file:
        if audio_file.content_type not in settings.ALLOWED_AUDIO_TYPES:
            return Response(
                {"error": f"Unsupported audio type: {audio_file.content_type}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if audio_file.size > settings.AUDIO_UPLOAD_MAX_SIZE:
            return Response({"error": "Audio file too large"}, status=status.HTTP_400_BAD_REQUEST)
        attachment = Attachment.objects.create(
            conversation=None,
            file_type=Attachment.FileType.AUDIO,
            file=audio_file,
            original_filename=audio_file.name,
        )
        attachment_id = str(attachment.id)

    payload = {
        "record_type": request.data.get("record_type"),
        "raw_text": request.data.get("raw_text", ""),
    }
    if attachment_id:
        payload["attachment_id"] = attachment_id

    serializer = CRMDraftCreateSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    draft = CRMDraft.objects.create(
        created_by=request.user,
        record_type=data["record_type"],
        raw_text=data.get("raw_text", ""),
        attachment_id=data.get("attachment_id"),
        status=CRMDraft.Status.PENDING,
    )
    # Audio path → transcribe + stop for review.
    # Text path → goes straight to extraction (handled inside the task).
    transcribe_crm_draft.delay(str(draft.id))
    return Response(CRMDraftSerializer(draft).data, status=status.HTTP_201_CREATED)


def _get_draft_or_404(request, draft_id):
    from .models import CRMDraft
    qs = CRMDraft.objects.all() if request.user.role == "admin" else CRMDraft.objects.filter(created_by=request.user)
    try:
        return qs.get(id=draft_id)
    except CRMDraft.DoesNotExist:
        return None


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([permissions.IsAuthenticated])
def crm_draft_detail(request, draft_id):
    from .serializers import CRMDraftSerializer, CRMDraftUpdateSerializer

    draft = _get_draft_or_404(request, draft_id)
    if not draft:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return Response(CRMDraftSerializer(draft).data)

    if request.method == "DELETE":
        draft.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    if draft.status == "submitted":
        return Response(
            {"error": "Cannot edit a draft that has been submitted."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    update_ser = CRMDraftUpdateSerializer(data=request.data)
    update_ser.is_valid(raise_exception=True)
    update_ser.update(draft, update_ser.validated_data)
    return Response(CRMDraftSerializer(draft).data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def crm_draft_extract(request, draft_id):
    """Kick off AI field extraction on a draft.

    Allowed when status is 'transcribed' (user reviewed transcript) or
    'failed' (retry). Optionally accepts an updated `raw_text` in the body
    so any edits the user made to the transcript are saved first.
    """
    from .serializers import CRMDraftSerializer
    from .tasks import extract_crm_draft

    draft = _get_draft_or_404(request, draft_id)
    if not draft:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)

    if draft.status not in ("transcribed", "failed", "pending"):
        return Response(
            {"error": f"Cannot start extraction from status '{draft.status}'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Allow the user to update the transcript before extraction
    new_text = request.data.get("raw_text")
    if new_text is not None:
        draft.raw_text = new_text
        draft.save(update_fields=["raw_text", "updated_at"])

    if not (draft.raw_text or "").strip():
        return Response(
            {"error": "Transcript is empty. Add text or re-upload the audio."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    extract_crm_draft.delay(str(draft.id))
    draft.refresh_from_db()
    return Response(CRMDraftSerializer(draft).data)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def crm_draft_submit(request, draft_id):
    from .serializers import CRMDraftSerializer
    from .services.zoho_fields import get_schema, module_for_record_type, required_fields
    from .models import ZohoCredential

    draft = _get_draft_or_404(request, draft_id)
    if not draft:
        return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)
    if draft.status == "submitted":
        return Response({"error": "Already submitted."}, status=status.HTTP_400_BAD_REQUEST)
    if draft.status not in ("ready", "failed"):
        return Response(
            {"error": f"Draft must be in 'ready' state, currently '{draft.status}'."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate required fields synchronously before kicking off submit
    cred = ZohoCredential.objects.filter(user_id=draft.created_by_id).first()
    if not cred:
        cred = ZohoCredential.objects.filter(user__role="admin").first()
    if not cred:
        return Response(
            {"error": "No Zoho connection available."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    schema = get_schema(cred, module_for_record_type(draft.record_type))
    missing = [api for api in required_fields(schema) if not draft.extracted_fields.get(api)]
    if missing:
        return Response(
            {"error": "Missing required fields", "missing_required": missing},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Run submit synchronously so the response carries the new record id.
    # The Zoho API call is fast (<2s) and the user is waiting on the result.
    from .services.zoho_sync import submit_draft_to_zoho
    try:
        submit_draft_to_zoho(draft, cred)
    except Exception as e:
        logger.error(f"CRMDraft submit failed for {draft.id}: {e}")
        return Response({"error": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
    draft.refresh_from_db()
    return Response(CRMDraftSerializer(draft).data)
