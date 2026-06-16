from django.urls import path
from . import views

urlpatterns = [
    path("integrations/zoho/status/", views.zoho_status, name="zoho-status"),
    path("integrations/zoho/connect/", views.zoho_connect, name="zoho-connect"),
    path("integrations/zoho/callback/", views.zoho_callback, name="zoho-callback"),
    path("integrations/zoho/disconnect/", views.zoho_disconnect, name="zoho-disconnect"),
    path("integrations/zoho/sync/", views.zoho_sync_now, name="zoho-sync"),
    path("integrations/gmail/status/", views.gmail_status, name="gmail-status"),
    path("integrations/gmail/connect/", views.gmail_connect, name="gmail-connect"),
    path("integrations/gmail/callback/", views.gmail_callback, name="gmail-callback"),
    path("integrations/gmail/disconnect/", views.gmail_disconnect, name="gmail-disconnect"),
    path("integrations/gmail/threads/", views.gmail_threads, name="gmail-threads"),
    path("integrations/gmail/threads/<str:thread_id>/", views.gmail_thread_detail, name="gmail-thread-detail"),

    # Lead/Account creation from conversation (CRMDraft flow)
    path("crm-drafts/", views.crm_drafts, name="crm-drafts"),
    path("crm-drafts/<uuid:draft_id>/", views.crm_draft_detail, name="crm-draft-detail"),
    path("crm-drafts/<uuid:draft_id>/extract/", views.crm_draft_extract, name="crm-draft-extract"),
    path("crm-drafts/<uuid:draft_id>/submit/", views.crm_draft_submit, name="crm-draft-submit"),
]
