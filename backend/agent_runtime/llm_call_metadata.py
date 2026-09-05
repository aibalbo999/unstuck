"""Anonymous key attribution and usage metadata for agent call events."""

from llm_client import extract_usage


def _key_slot_fields(rotator, api_key: str | None) -> dict:
    keys = list(getattr(rotator, "keys", []) or [])
    if not keys:
        return {}
    fields = {"key_count": len(keys)}
    if api_key:
        try:
            fields["key_slot"] = keys.index(api_key) + 1
        except ValueError:
            pass
    return fields


def _record_llm_token_usage(context, agent_num: int, response) -> None:
    usage = extract_usage(response)
    if usage:
        context.setdefault("llm_token_usage", {})[agent_num] = usage
