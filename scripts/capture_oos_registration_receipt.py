#!/usr/bin/env python3
"""Capture a bounded Git remote receipt for a committed prospective OOS manifest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from oos_research.manifest import validate_manifest
from oos_research.provenance import verify_registration_capture_receipt


COMMIT_RE = re.compile(r"[0-9a-f]{40}")
REMOTE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
RunResult = tuple[int, bytes, bytes]


def _run(command: list[str], *, timeout: int = 15) -> RunResult:
    try:
        completed = subprocess.run(command, capture_output=True, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Git receipt command could not be executed") from exc
    return completed.returncode, completed.stdout, completed.stderr


def _checked(run: Callable[..., RunResult], command: list[str], *, label: str) -> bytes:
    code, stdout, _stderr = run(command, timeout=15)
    if code != 0:
        raise RuntimeError(f"Git receipt {label} failed")
    return stdout


def _safe_repo_path(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("manifest repo path must be a non-empty POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", "..", ".git"} for part in path.parts):
        raise ValueError("manifest repo path must stay inside the repository")
    return str(path)


def _has_symlink_between(path: Path, root: Path) -> bool:
    cursor = path
    while True:
        if cursor.is_symlink():
            return True
        if cursor == root:
            return False
        if cursor == cursor.parent or root not in cursor.parents:
            return True
        cursor = cursor.parent


def capture(
    *,
    manifest_path: Path,
    repo_root: Path,
    manifest_repo_path: str,
    remote: str,
    ref: str,
    expected_commit: str,
    observed_at: str | None = None,
    run: Callable[..., RunResult] = _run,
) -> dict:
    if not repo_root.is_absolute() or repo_root.is_symlink() or not repo_root.is_dir():
        raise ValueError("repo root must be an existing absolute non-symlink directory")
    repo_root = repo_root.resolve()
    repo_path = _safe_repo_path(manifest_repo_path)
    expected_manifest_path = repo_root.joinpath(*PurePosixPath(repo_path).parts)
    if (
        not manifest_path.is_absolute()
        or manifest_path.resolve() != expected_manifest_path.resolve()
        or not manifest_path.is_file()
        or _has_symlink_between(manifest_path, repo_root)
    ):
        raise ValueError("manifest path must be the exact non-symlink repository file")
    if not REMOTE_RE.fullmatch(remote):
        raise ValueError("remote must be a safe configured remote name")
    if (
        not isinstance(ref, str)
        or not ref.startswith(("refs/heads/", "refs/tags/"))
        or any(character.isspace() for character in ref)
    ):
        raise ValueError("ref must be an explicit heads or tags ref")
    if not COMMIT_RE.fullmatch(expected_commit):
        raise ValueError("expected commit must be a lowercase 40-character Git commit")

    manifest_bytes = manifest_path.read_bytes()
    try:
        manifest = json.loads(manifest_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("prospective manifest must be valid UTF-8 JSON") from exc
    validate_manifest(manifest)
    if manifest.get("study_kind") != "prospective":
        raise ValueError("registration receipt requires a prospective manifest")

    git = ["git", "-C", str(repo_root)]
    top = _checked(run, [*git, "rev-parse", "--show-toplevel"], label="repository check").decode("utf-8").strip()
    if Path(top).resolve() != repo_root:
        raise RuntimeError("Git receipt repository root does not match")
    head = _checked(run, [*git, "rev-parse", "HEAD"], label="HEAD check").decode("ascii").strip()
    if head != expected_commit:
        raise RuntimeError("Git receipt expected commit is not the current HEAD")
    status = _checked(
        run,
        [*git, "status", "--porcelain=v1", "--untracked-files=normal"],
        label="worktree check",
    )
    if status.strip():
        raise RuntimeError("Git receipt requires a clean worktree")
    committed_manifest = _checked(
        run, [*git, "show", f"{expected_commit}:{repo_path}"], label="committed manifest check"
    )
    if committed_manifest != manifest_bytes:
        raise RuntimeError("Git receipt manifest bytes differ from the expected commit")
    remote_url = _checked(
        run, [*git, "remote", "get-url", remote], label="remote URL check"
    ).decode("utf-8").strip()
    remote_evidence = _checked(
        run, [*git, "ls-remote", "--refs", remote, ref], label="remote ref check"
    )
    expected_evidence = f"{expected_commit}\t{ref}\n".encode("utf-8")
    if remote_evidence != expected_evidence:
        raise RuntimeError("Git remote ref does not point to the expected commit")

    receipt = {
        "external_registration_receipt": {
            "schema_version": "oos.registration-receipt.v1",
            "source": "git_remote",
            "remote_url": remote_url,
            "ref": ref,
            "commit": expected_commit,
            "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": manifest["manifest_sha256"],
            "remote_evidence": remote_evidence.decode("utf-8"),
            "remote_evidence_sha256": hashlib.sha256(remote_evidence).hexdigest(),
        }
    }
    reasons = verify_registration_capture_receipt(
        receipt, manifest_sha256=manifest["manifest_sha256"]
    )
    if reasons:
        raise ValueError(f"Git receipt is invalid: {', '.join(reasons)}")
    return receipt


def validate_output_path(path: Path, *, forbidden_root: Path | None = None) -> Path:
    if not path.is_absolute() or path.exists() or path.is_symlink() or not path.parent.is_dir():
        raise ValueError("receipt output must be a new absolute path in an existing directory")
    resolved = path.parent.resolve() / path.name
    if forbidden_root is not None:
        root = forbidden_root.resolve()
        if resolved == root or root in resolved.parents:
            raise ValueError("receipt output must stay outside the repository")
    return resolved


def write_exclusive(path: Path, payload: dict, *, forbidden_root: Path | None = None) -> None:
    path = validate_output_path(path, forbidden_root=forbidden_root)
    encoded = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, 0o600)
    try:
        view = memoryview(encoded)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("short registration receipt write")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--manifest-repo-path", required=True)
    parser.add_argument("--remote", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = validate_output_path(args.output, forbidden_root=args.repo)
    payload = capture(
        manifest_path=args.manifest,
        repo_root=args.repo,
        manifest_repo_path=args.manifest_repo_path,
        remote=args.remote,
        ref=args.ref,
        expected_commit=args.expected_commit,
    )
    write_exclusive(output, payload, forbidden_root=args.repo)
    print(json.dumps({
        "status": "captured",
        "manifest_sha256": payload["external_registration_receipt"]["manifest_sha256"],
        "commit": payload["external_registration_receipt"]["commit"],
        "ref": payload["external_registration_receipt"]["ref"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
