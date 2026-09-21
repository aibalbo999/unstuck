"""Provider response text extraction shared by transport and diagnostics callers."""
from llm_http_providers import TextLLMResponse


def response_text(response) -> str:
    """Extract text from a Google GenAI response without leaking object internals."""
    if isinstance(response, TextLLMResponse):
        return response.text

    candidates = getattr(response, "candidates", None) or []
    parts = []
    saw_candidate_parts = False
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        for part in getattr(content, "parts", []) or []:
            saw_candidate_parts = True
            if getattr(part, "thought", False):
                continue
            part_text = getattr(part, "text", None)
            if part_text:
                parts.append(part_text)
    if saw_candidate_parts:
        return "\n".join(parts)

    try:
        text = getattr(response, "text", None)
    except Exception:
        text = None
    return text or ""
