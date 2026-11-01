"""Process-local frozen-input seam; NOT a canary launcher or authorization.

Only a trusted, isolated controller may install this scope, inside its async job
wrapper. The controller still owns source qualification, maintenance authority,
exact paths, SDK/HTTP budgets, a zero-retry queue payload and process cleanup.
No API field, environment switch, file loader or serialized job flag enables it.

Publication is blocked by default. A trusted controller can bind an existing
private output directory for create-only diagnostic artifacts; that does not
establish a qualified sample or formal release authority. These input guards
are not a network or filesystem sandbox and authorize no live provider call.
"""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import canary_release_policy


class FrozenCanaryError(RuntimeError):
    """Fail closed without interpreting input metadata as permission."""


class FrozenCanaryPublicationPending(FrozenCanaryError):
    pass


_active: ContextVar = ContextVar("analysis_frozen_canary", default=None)
_MAX_SOURCE_BYTES = 32 * 1024 * 1024


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise FrozenCanaryError("duplicate frozen source key")
        result[key] = value
    return result


def _finite_float(value):
    result = float(value)
    if not math.isfinite(result):
        raise FrozenCanaryError("non-finite frozen source number")
    return result


def _invalid_constant(value):
    raise FrozenCanaryError("non-finite frozen source constant")


def _decode(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_float=_finite_float, parse_constant=_invalid_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise FrozenCanaryError("invalid frozen source JSON") from exc


def _digest_data(data):
    try:
        raw = json.dumps(data, sort_keys=True, ensure_ascii=True,
                         separators=(",", ":"), allow_nan=False).encode("ascii")
    except (TypeError, ValueError, RecursionError) as exc:
        raise FrozenCanaryError("invalid derived frozen workflow data") from exc
    return hashlib.sha256(raw).hexdigest()


def _owner():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return os.getpid(), threading.get_ident(), task


@dataclass(frozen=True)
class _Binding:
    campaign_id: str
    job_id: str
    ticker: str
    pipeline_id: str
    source_json: bytes
    source_sha256: str
    manifest_sha256: str


class _Scope:
    def __init__(self, binding, boundary_check, publication_output_dir, workflow_rotator, publication_validator):
        self.binding = binding
        self._boundary_check = boundary_check
        self._owner = _owner()
        self._live = True
        self._claimed = False
        self._workflow_started = False
        self._checkpoint_started = False
        self._checkpoint_path = None
        self._workflow_sha256 = None
        self._publication_started = False
        self._publication_root = None
        self._publication_identity = None
        self._workflow_rotator = workflow_rotator
        self._publication_validator = publication_validator
        if publication_output_dir is not None:
            root = Path(publication_output_dir)
            if not root.is_absolute() or root.is_symlink():
                raise FrozenCanaryError("private publication requires an absolute nonsymlink directory")
            self._publication_root = root
            self._publication_identity = self._root_identity()

    def _root_identity(self):
        try:
            info = self._publication_root.lstat()
        except OSError as exc:
            raise FrozenCanaryError("private publication directory unavailable") from exc
        if not stat.S_ISDIR(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o700:
            raise FrozenCanaryError("private publication directory must already exist with mode 0700")
        return info.st_dev, info.st_ino

    def check(self, stage, job_id=None):
        # Graph child tasks legitimately inherit this scope; admission does not.
        if (not self._live or _owner()[:2] != self._owner[:2]
                or (job_id is not None and job_id != self.binding.job_id)):
            raise FrozenCanaryError("expired or mismatched frozen canary scope")
        if self._boundary_check(stage) is not True:
            raise FrozenCanaryError("frozen canary boundary not confirmed")
        if self._publication_root is not None and self._root_identity() != self._publication_identity:
            raise FrozenCanaryError("private publication directory identity changed")

    def claim(self, job_id, ticker, pipeline_id, force_refresh):
        binding = self.binding
        if (self._claimed or _owner() != self._owner
                or (job_id, ticker, pipeline_id) !=
                (binding.job_id, binding.ticker, binding.pipeline_id)
                or force_refresh is not False):
            raise FrozenCanaryError("frozen canary job binding mismatch or reuse")
        self.check("job_admission", job_id)
        self._claimed = True
        return self

    def data(self):
        self.check("read_frozen_source")
        if not self._claimed:
            raise FrozenCanaryError("frozen canary job not admitted")
        return _decode(self.binding.source_json)

    def bind_workflow_data(self, data):
        self.check("bind_workflow_data")
        if not self._claimed or self._workflow_sha256 is not None:
            raise FrozenCanaryError("frozen workflow data already bound")
        self._workflow_sha256 = _digest_data(data)

    def receipt(self):
        return {"campaign_id": self.binding.campaign_id,
                "source_sha256": self.binding.source_sha256,
                "manifest_sha256": self.binding.manifest_sha256,
                "workflow_data_sha256": self._workflow_sha256,
                "private_publication_enabled": self._publication_root is not None,
                "production_ready": False, "publication_authorized": False}

    def validate_workflow(self, request):
        self.check("before_workflow_services")
        binding = self.binding
        if (not self._claimed or self._workflow_started
                or request.thread_id != f"{binding.job_id}:{binding.pipeline_id}"
                or request.pipeline_id != binding.pipeline_id
                or self._workflow_sha256 != _digest_data(request.data)):
            raise FrozenCanaryError("frozen workflow binding mismatch or reuse")
        if (request.checkpointer is not None or request.checkpoint_backend != "sqlite"
                or not request.checkpoint_path or not Path(request.checkpoint_path).is_absolute()):
            raise FrozenCanaryError("frozen canary requires a controller-owned SQLite checkpoint path")

    def services(self, services, request):
        self.validate_workflow(request)
        self._workflow_started = True
        self._checkpoint_path = os.fspath(request.checkpoint_path)

        async def prepare(state):
            self.check("frozen_prepare")
            return {"rag_status": {"status": "unavailable",
                    "reason": "frozen_replay_no_original_rag_index",
                    "exact_original_prompt_replay": False}}

        async def repair(state):
            self.check("frozen_repair")
            return {"tool_results": {"official_reconciliation": {
                "status": "unavailable", "reason": "frozen_replay_external_refresh_forbidden"}}}

        return replace(services, prepare=prepare, repair=repair)

    def block_publication(self):
        self.check("before_publication")
        raise FrozenCanaryPublicationPending(
            "凍結 canary 的維護控制與不可覆寫發布尚未整合；未寫入報告。")

    def publication_options(self, *, context, output_dir, filename):
        if self._publication_root is None:
            self.block_publication()
        self.check("before_private_publication")
        from analysis_job_helpers import stable_report_filename
        expected = stable_report_filename(self.binding.job_id, self.binding.ticker, self.binding.pipeline_id)
        if (not self._claimed or self._publication_started or _owner() != self._owner
                or Path(output_dir) != self._publication_root or filename != expected
                or context.get("ticker") != self.binding.ticker
                or context.get("pipeline_id") != self.binding.pipeline_id
                or self._workflow_sha256 is None
                or _digest_data(context.get("data")) != self._workflow_sha256):
            raise FrozenCanaryError("private publication binding mismatch or reuse")
        self._publication_started = True
        return {"create_only": True}

    def close(self):
        self._live = False

    def claim_checkpoint(self, thread_id, backend, path):
        self.check("before_checkpoint_readback")
        if (not self._workflow_started or self._checkpoint_started or backend != "sqlite"
                or os.fspath(path) != self._checkpoint_path
                or thread_id != f"{self.binding.job_id}:{self.binding.pipeline_id}"):
            raise FrozenCanaryError("frozen checkpoint binding mismatch or reuse")
        self._checkpoint_started = True


@contextmanager
def frozen_canary_inputs(*, campaign_id, job_id, ticker, pipeline_id,
                         source_json, source_sha256, manifest_sha256, boundary_check,
                         publication_output_dir=None, workflow_rotator=None, publication_validator=None):
    """Install one immutable input binding, without granting execution authority."""
    canary_release_policy.require_canary_enabled()
    if _active.get() is not None or _owner()[2] is None:
        raise FrozenCanaryError("frozen canary requires a non-nested async owner")
    for value in (campaign_id, job_id, ticker):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
            raise FrozenCanaryError("invalid frozen canary identity")
    if ticker != ticker.strip().upper() or pipeline_id not in ("v1", "v2", "v3", "v4"):
        raise FrozenCanaryError("frozen canary requires one exact ticker and mode")
    for digest in (source_sha256, manifest_sha256):
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise FrozenCanaryError("invalid frozen canary digest")
    if (type(source_json) is not bytes or not 0 < len(source_json) <= _MAX_SOURCE_BYTES
            or hashlib.sha256(source_json).hexdigest() != source_sha256):
        raise FrozenCanaryError("frozen source bytes or digest mismatch")
    data = _decode(source_json)
    if (not isinstance(data, dict) or data.get("ticker") != ticker
            or not isinstance(data.get("fetch_date"), str) or not data["fetch_date"].strip()
            or not isinstance(data.get("data_trust"), dict)):
        raise FrozenCanaryError("frozen source identity, date or trust missing")
    try:
        cutoff = datetime.fromisoformat(data["analysis_input_cutoff"])
        if cutoff.utcoffset() is None:
            raise ValueError("missing timezone")
    except (KeyError, TypeError, ValueError) as exc:
        raise FrozenCanaryError("frozen source requires its original aware input cutoff") from exc
    if not callable(boundary_check):
        raise FrozenCanaryError("frozen canary requires a controller boundary check")
    if publication_validator is not None and not callable(publication_validator):
        raise FrozenCanaryError("private publication validator must be callable")
    binding = _Binding(campaign_id, job_id, ticker, pipeline_id, source_json,
                       source_sha256, manifest_sha256)
    scope = _Scope(binding, boundary_check, publication_output_dir, workflow_rotator, publication_validator)
    token = _active.set(scope)
    try:
        yield
    finally:
        scope.close()
        _active.reset(token)


def claim_frozen_canary(job_id, ticker, pipeline_id, force_refresh):
    scope = _active.get()
    if scope is not None:
        canary_release_policy.require_canary_enabled()
    return None if scope is None else scope.claim(job_id, ticker, pipeline_id, force_refresh)


def check_frozen_canary(job_id):
    scope = _active.get()
    if scope is not None:
        scope.check("job_progress", job_id)


def frozen_workflow_services(services, request):
    scope = _active.get()
    return services if scope is None else scope.services(services, request)


def check_frozen_workflow_request(request):
    scope = _active.get()
    if scope is not None:
        scope.validate_workflow(request)


def frozen_workflow_rotator(request):
    """Use the controller's shared-quota rotator before any default construction.

    This is process-local injection, not a quota assertion or permission switch.
    The controller must install its SDK/HTTP budget and validate the limiter.
    """
    scope = _active.get()
    if scope is None:
        return None
    scope.validate_workflow(request)
    return scope._workflow_rotator


def check_frozen_report_bundle(bundle):
    scope = _active.get()
    if scope is not None:
        scope.check("before_private_bundle_write")
        if not scope._publication_started or _owner() != scope._owner:
            raise FrozenCanaryError("private report bundle has no admitted publication")
        if scope._publication_validator is not None and scope._publication_validator(bundle) is not True:
            raise FrozenCanaryError("private report bundle validation failed")


def claim_frozen_checkpoint(thread_id, backend, path):
    scope = _active.get()
    if scope is None:
        return False
    scope.claim_checkpoint(thread_id, backend, path)
    return True


def frozen_canary_rag_status():
    scope = _active.get()
    if scope is None:
        return None
    scope.check("frozen_rag_unavailable")
    if not scope._claimed:
        raise FrozenCanaryError("frozen canary job not admitted")
    return {"status": "unavailable", "reason": "frozen_replay_no_original_rag_index",
            "exact_original_prompt_replay": False}
