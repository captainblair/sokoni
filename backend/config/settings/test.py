"""
Test settings.

Identical to local settings except for deliberate speed trade-offs that are
safe because they never run outside the test suite.
"""

from .local import *  # noqa: F401,F403,F405

# PBKDF2 is intentionally slow. Every fixture that creates a user pays that
# cost, so tests use a cheap hasher instead.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Nothing in the suite renders a template or serves a static asset.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEBUG = False

# The suite is not a load test. Limits stay in force in local and production;
# here they are raised so a legitimate test run cannot 429 itself.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        "anon": "10000/min",
        "user": "10000/min",
        "auth": "10000/min",
        "agent": "10000/min",
    },
}
