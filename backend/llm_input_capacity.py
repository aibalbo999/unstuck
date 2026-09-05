"""Non-retryable admission checks for one request, independent of key rotation."""

from __future__ import annotations

import math


class InputCapacityExceededError(ValueError):
    def __init__(self, model, estimated_input_tokens, limit, basis):
        super().__init__(f"模型 {model} 本次預估輸入 {estimated_input_tokens} tokens 超過可用輸入預算 {limit}（{basis}）；需縮減來源或改用合適路由。")
        self.model = model
        self.estimated_input_tokens = estimated_input_tokens
        self.limit = limit
        self.basis = basis


def ensure_input_capacity(model, estimated_input_tokens, *, input_limit=0, tpm_limit=0):
    """Do not reserve or sleep for input that cannot fit even an empty window."""
    for limit, basis in ((input_limit, "local_input_budget"), (tpm_limit, "configured_input_tpm")):
        if limit and limit > 0 and estimated_input_tokens > limit:
            raise InputCapacityExceededError(model, estimated_input_tokens, limit, basis)


def estimate_input_tokens(text):
    """Conservative mixed-language estimate, not a provider tokenizer or quota."""
    ascii_chars = sum(ord(char) < 128 for char in text)
    non_ascii_bytes = len(text.encode("utf-8")) - ascii_chars
    return max(1, math.ceil(ascii_chars / 3 + non_ascii_bytes / 2))


def estimate_text_tokens(text: str, response_budget: int = 0) -> int:
    """Legacy character estimate retained for existing prompt-size contracts."""
    if not text:
        return max(response_budget, 1)
    return max(int(len(text) / 3.5) + response_budget, 1)
