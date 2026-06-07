"""Deprecated compatibility alias for the core assembler."""

from __future__ import annotations

import sys

from . import core_assembler as _assembler

sys.modules[__name__] = _assembler
