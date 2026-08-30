"""
Settings package.

Default to local development settings. Override with DJANGO_SETTINGS_MODULE
or DJANGO_ENV when deploying.
"""

import os

_env = os.getenv("DJANGO_ENV", "local").lower()

if _env == "production":
    from .production import *  # noqa: F401,F403
else:
    from .local import *  # noqa: F401,F403
