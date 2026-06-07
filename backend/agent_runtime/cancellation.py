"""Cooperative cancellation helpers for long-running agent jobs."""

from __future__ import annotations

from typing import Callable, MutableMapping, Optional


CANCEL_CHECK_CONTEXT_KEY = "_cancel_check"


def attach_cancel_check(context: MutableMapping, cancel_check: Optional[Callable[[], None]]) -> None:
    if callable(cancel_check):
        context[CANCEL_CHECK_CONTEXT_KEY] = cancel_check


def raise_if_cancelled(context: MutableMapping | None) -> None:
    if not isinstance(context, MutableMapping):
        return
    cancel_check = context.get(CANCEL_CHECK_CONTEXT_KEY)
    if callable(cancel_check):
        cancel_check()
