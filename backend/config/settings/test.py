"""
Test settings.

Identical to local settings except for deliberate speed trade-offs that are
safe because they never run outside the test suite.
"""

from .local import *  # noqa: F401,F403

# PBKDF2 is intentionally slow. Every fixture that creates a user pays that
# cost, so tests use a cheap hasher instead.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Nothing in the suite renders a template or serves a static asset.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

DEBUG = False
