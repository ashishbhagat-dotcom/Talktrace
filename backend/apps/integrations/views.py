import logging

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import ZohoCredential
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
    cred = _get_org_credential()
    if cred:
        return Response({
            "connected": True,
            "zoho_user_email": cred.zoho_user_email,
            "last_sync_at": cred.last_sync_at,
        })
    return Response({"connected": False})


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def zoho_connect(request):
    if request.user.role != "admin":
        return Response(
            {"error": "Only admins can connect Zoho CRM."},
            status=status.HTTP_403_FORBIDDEN,
        )
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
    if request.user.role != "admin":
        return Response(
            {"error": "Only admins can disconnect Zoho CRM."},
            status=status.HTTP_403_FORBIDDEN,
        )
    ZohoCredential.objects.filter(user__role="admin").delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def zoho_sync_now(request):
    if request.user.role != "admin":
        return Response(
            {"error": "Only admins can trigger Zoho sync."},
            status=status.HTTP_403_FORBIDDEN,
        )
    cred = _get_org_credential()
    if not cred:
        return Response({"error": "Not connected to Zoho"}, status=status.HTTP_400_BAD_REQUEST)

    from .tasks import sync_zoho_for_user
    sync_zoho_for_user.delay(str(cred.user_id))
    return Response({"status": "sync started"})
