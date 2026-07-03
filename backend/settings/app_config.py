"""Compatibility aggregator for grouped application settings."""

from __future__ import annotations

from importlib import import_module

from .runtime_validation import validate_runtime_settings_from


_SETTING_MODULE_NAMES = ("models", "providers", "runtime_limits", "security", "storage")
_EXPORTED_SETTING_NAMES: list[str] = []
for module_name in _SETTING_MODULE_NAMES:
    module = import_module(f".{module_name}", __package__)
    for name in getattr(module, "__all__", ()):
        globals()[name] = getattr(module, name)
        if name not in _EXPORTED_SETTING_NAMES:
            _EXPORTED_SETTING_NAMES.append(name)


def validate_runtime_settings() -> list[str]:
    """Return startup configuration warnings without exposing secrets."""
    return validate_runtime_settings_from(globals())


__all__ = sorted({
    *_EXPORTED_SETTING_NAMES,
    "validate_runtime_settings",
})
