"""Fail-closed Docker profile for synthetic OOS validation."""

from __future__ import annotations

import re
from typing import Any


BASE_IMAGE = "sha256:9d2e5553305c7c7b0097999bb17187c69b921ccd6bc9d40e4bb5ebe652c00285"
_RUN_RE = re.compile(r"^[0-9a-f]{16}$")
_IMAGE_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def create_args(run_id: str, image_id: str) -> list[str]:
    if not _RUN_RE.fullmatch(run_id) or not _IMAGE_RE.fullmatch(image_id):
        raise ValueError("isolated_oos_identity_invalid")
    return [
        "docker", "create", "--name", f"stock-agent-oos-{run_id}",
        "--label", f"stock-agent.oos-validation.run={run_id}", "--network", "none",
        "--ipc", "private", "--restart", "no", "--read-only", "--user", "65532:65532",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--pids-limit", "128",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=256m,mode=1777",
        "--tmpfs", "/results:rw,nosuid,nodev,size=2m,uid=65532,gid=65532,mode=0700",
        image_id, run_id,
    ]


def validate_container(info: Any, run_id: str, image_id: str) -> None:
    try:
        config, host = info["Config"], info["HostConfig"]
        labels = config["Labels"]
        valid = (
            info["Image"] == image_id and config["User"] == "65532:65532"
            and labels.get("stock-agent.oos-validation.run") == run_id
            and host["NetworkMode"] == "none" and host["Privileged"] is False
        )
        valid = valid and not host.get("Binds") and not info.get("Mounts") and not host.get("PortBindings")
        valid = valid and host.get("ReadonlyRootfs") is True and host.get("CapDrop") == ["ALL"]
        valid = valid and host.get("SecurityOpt") == ["no-new-privileges:true"]
        valid = valid and host.get("Tmpfs") == {
            "/tmp": "rw,nosuid,nodev,size=256m,mode=1777",
            "/results": "rw,nosuid,nodev,size=2m,uid=65532,gid=65532,mode=0700",
        }
        if not valid:
            raise ValueError("isolated_oos_container_rejected")
    except (KeyError, TypeError, AttributeError):
        raise ValueError("isolated_oos_container_rejected") from None
