"""Provider-prefixed LLM model route parsing."""

from __future__ import annotations


PROVIDER_ALIASES = {
    "anthropic": "anthropic",
    "claude": "anthropic",
    "gemini": "google",
    "google": "google",
    "openai": "openai",
}


def split_model_provider(model_id: str) -> tuple[str, str]:
    """Return ``(provider, provider_model_id)`` for a configured model route."""
    raw = str(model_id or "").strip()
    if ":" not in raw:
        return "google", raw
    provider_prefix, provider_model = raw.split(":", 1)
    provider = PROVIDER_ALIASES.get(provider_prefix.strip().lower(), provider_prefix.strip().lower())
    return provider or "google", provider_model.strip()


def provider_for_model(model_id: str) -> str:
    return split_model_provider(model_id)[0]
