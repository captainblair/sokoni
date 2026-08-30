from django.db import connection
from django.db.utils import OperationalError
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(tags=["health"], auth=[])
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
