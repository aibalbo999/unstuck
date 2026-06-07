"""Compatibility facade for application settings.

New code may import grouped settings from backend/settings. Existing modules
can continue importing constants from config without behavior changes.
"""

from settings.app_config import *  # noqa: F401,F403
