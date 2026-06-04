from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

urlpatterns = [
    path("admin/", admin.site.urls),

    # API auth
    path("api/auth/", include("apps.accounts.urls")),

    # App APIs
    path("api/", include("apps.conversations.urls")),
    path("api/", include("apps.customers.urls")),
    path("api/", include("apps.search.urls")),
    path("api/", include("apps.analytics.urls")),
    path("api/", include("apps.integrations.urls")),

    # API Docs
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
