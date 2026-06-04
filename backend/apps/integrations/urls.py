from django.urls import path
from . import views

urlpatterns = [
    path("integrations/zoho/status/", views.zoho_status, name="zoho-status"),
    path("integrations/zoho/connect/", views.zoho_connect, name="zoho-connect"),
    path("integrations/zoho/callback/", views.zoho_callback, name="zoho-callback"),
    path("integrations/zoho/disconnect/", views.zoho_disconnect, name="zoho-disconnect"),
    path("integrations/zoho/sync/", views.zoho_sync_now, name="zoho-sync"),
]
