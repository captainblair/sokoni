from django.apps import AppConfig


class AgentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agent"
    label = "agent"
    verbose_name = "Agent"

    def ready(self):
        # Importing for the side effect of registering every tool, so the
        # registry is complete before the first request arrives.
        from apps.agent import tools  # noqa: F401
