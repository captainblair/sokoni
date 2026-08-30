from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny

schema_kwargs = {
    "permission_classes": [AllowAny],
    "authentication_classes": [],
    "throttle_classes": [],
}

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(**schema_kwargs), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", **schema_kwargs),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema", **schema_kwargs),
        name="redoc",
    ),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.businesses.urls")),
    path("api/v1/", include("apps.parties.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.ledger.urls")),
    path("api/v1/", include("apps.debts.urls")),
    path("api/v1/", include("apps.finance.urls")),
    path("api/v1/", include("apps.agent.urls")),
    path("api/v1/", include("apps.audit.urls")),
]
