from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.businesses.urls")),
    path("api/v1/", include("apps.parties.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.ledger.urls")),
    path("api/v1/", include("apps.debts.urls")),
    path("api/v1/", include("apps.finance.urls")),
    path("api/v1/", include("apps.agent.urls")),
]
