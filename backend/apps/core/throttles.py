"""
Named rate limits.

Auth is tighter than the rest of the API because a guessed password is a stolen
business. The agent door is tighter than ordinary reads because a runaway client
— or a future voice pipeline stuck in a loop — would otherwise write money as
fast as it could speak.
"""

from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle


class NamedRateThrottle(SimpleRateThrottle):
    """
    A throttle whose rate is looked up from settings by `scope`.

    Rates are read at check time rather than at import, so a settings change
    (and the test suite's raised limits) actually takes effect.
    """

    def get_rate(self):
        return api_settings.DEFAULT_THROTTLE_RATES[self.scope]

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            ident = request.user.pk
        else:
            ident = self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}


class AuthRateThrottle(NamedRateThrottle):
    scope = "auth"


class AgentRateThrottle(NamedRateThrottle):
    scope = "agent"
