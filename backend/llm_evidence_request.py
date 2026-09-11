"""Request-local source fidelity and cache isolation for evidence extraction."""
from contextlib import contextmanager
from contextvars import ContextVar

from google_prompt_safety import GOOGLE_SAFE_PROMPT_PREFIX, append_google_genai_disclaimer

_exact_source = ContextVar("llm_exact_evidence_source", default=False)


def is_evidence_request():
    return _exact_source.get()


def frame_source_prompt(prompt):
    # Preserve source values verbatim; keep the normal research safety framing.
    return append_google_genai_disclaimer(GOOGLE_SAFE_PROMPT_PREFIX + "\n\n" + prompt)


@contextmanager
def evidence_request_scope():
    token = _exact_source.set(True)
    try:
        yield
    finally:
        _exact_source.reset(token)
