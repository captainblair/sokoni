from django.db import connection
from django.db.utils import OperationalError
from drf_spectacular.renderers import (
    OpenApiJsonRenderer,
    OpenApiJsonRenderer2,
    OpenApiYamlRenderer,
    OpenApiYamlRenderer2,
)
from drf_spectacular.utils import extend_schema
from drf_spectacular.views import SpectacularAPIView
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.schema import HealthCheckSerializer


@extend_schema(tags=["health"], auth=[], responses=HealthCheckSerializer)
class HealthCheckView(APIView):
    """
    Lightweight liveness/readiness probe for local Docker and Render.
    """

    authentication_classes = []
    permission_classes = []

    def get(self, request):
        db_ok = False
        db_error = None

        try:
            connection.ensure_connection()
            db_ok = True
        except OperationalError as exc:
            db_error = str(exc)

        payload = {
            "status": "ok" if db_ok else "degraded",
            "service": "sokoni-api",
            "database": "up" if db_ok else "down",
        }
        if db_error and request.query_params.get("verbose") == "1":
            payload["database_error"] = db_error

        http_status = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=http_status)


class PublicSchemaView(SpectacularAPIView):
    """
    OpenAPI document for Swagger / ReDoc.

    Generated without the browser request so a session cookie, Authorization
    header, or dead database connection cannot turn documentation into a 500.
    JSON is preferred because Swagger UI asks for application/json.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []
    serve_public = True
    renderer_classes = [
        OpenApiJsonRenderer2,
        OpenApiJsonRenderer,
        OpenApiYamlRenderer2,
        OpenApiYamlRenderer,
    ]

    def _get_schema_response(self, request):
        version = self.api_version or request.version or self._get_version_parameter(request)
        generator = self.generator_class(
            urlconf=self.urlconf, api_version=version, patterns=self.patterns
        )
        return Response(
            data=generator.get_schema(request=None, public=True),
            headers={
                "Content-Disposition": (
                    f'inline; filename="{self._get_filename(request, version)}"'
                )
            },
        )
