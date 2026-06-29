"""Compatibility shim for RQ jobs enqueued as ``analysis_jobs.*``.

RQ workers may be started from the repository root while the implementation
modules live under ``backend/`` and use top-level imports such as ``config``.
Keep this root module importable so existing Redis jobs can still resolve.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
IMPL_PATH = BACKEND_DIR / "analysis_jobs.py"
IMPL_MODULE_NAME = "_stock_agent_backend_analysis_jobs"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_spec = importlib.util.spec_from_file_location(IMPL_MODULE_NAME, IMPL_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Unable to load backend analysis_jobs implementation from {IMPL_PATH}")

_impl = importlib.util.module_from_spec(_spec)
sys.modules[IMPL_MODULE_NAME] = _impl
_spec.loader.exec_module(_impl)

run_stock_analysis_job = _impl.run_stock_analysis_job
run_stock_analysis_job_async = _impl.run_stock_analysis_job_async
AnalysisJobCancelled = _impl.AnalysisJobCancelled

run_stock_analysis_job.__module__ = __name__
run_stock_analysis_job_async.__module__ = __name__


def __getattr__(name: str):
    return getattr(_impl, name)


def __dir__() -> list[str]:
    return sorted({*globals(), *dir(_impl)})


__all__ = [
    "AnalysisJobCancelled",
    "run_stock_analysis_job",
    "run_stock_analysis_job_async",
]
