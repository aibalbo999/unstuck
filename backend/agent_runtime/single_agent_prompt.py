"""Temporary prompt-context overrides for one routed model attempt."""

def build_model_prompt(agent_num, data, context, model_id, compact_primary, *, prompt_builder):
    keys = ("_primary_probe_prompt", "_prompt_model_id")
    previous = {key: context[key] for key in keys if key in context}
    try:
        context["_primary_probe_prompt"] = compact_primary
        context["_prompt_model_id"] = model_id
        return prompt_builder(agent_num, data, context)
    finally:
        for key in keys:
            if key in previous:
                context[key] = previous[key]
            else:
                context.pop(key, None)
