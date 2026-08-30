from django.urls import path

from apps.agent.views import ExecuteToolView, ToolRegistryView

urlpatterns = [
    path("agent/tools/", ToolRegistryView.as_view(), name="agent-tools"),
    path("agent/execute/", ExecuteToolView.as_view(), name="agent-execute"),
]
