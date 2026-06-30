"""Compatibility facade for application settings.

New code may import grouped settings from backend/settings. Existing modules
can continue importing constants from config without behavior changes.
"""

from settings import app_config as _app_config


__all__ = list(_app_config.__all__)

for _name in __all__:
    globals()[_name] = getattr(_app_config, _name)
