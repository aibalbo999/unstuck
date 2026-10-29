"""Anonymous key attribution and usage metadata for agent call events."""

from llm_client import extract_usage


def _key_slot_fields(rotator, api_key: str | None) -> dict:
    from llm_observation_context import key_identity
    keys = list(getattr(rotator, "keys", []) or [])
    if not keys:
        return {}
    fields = {"key_count": len(keys)}
    if api_key:
        try:
            fields["key_slot"] = keys.index(api_key) + 1
        except ValueError:
            pass
    if api_key:
        fields.update(key_identity(api_key, 'google:unknown'))
        # The executing rotator, not global API ordering, owns this slot.
        if api_key in keys:
            fields['key_slot'] = keys.index(api_key)+1
        fields['key_count'] = len(keys)
    return fields


def _record_llm_token_usage(context, agent_num: int, response) -> None:
    usage = extract_usage(response)
    if usage:
        context.setdefault("llm_token_usage", {})[agent_num] = usage
