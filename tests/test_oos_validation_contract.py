from __future__ import annotations

import copy

import pytest

from oos_validation.launcher import BASE_IMAGE, create_args, validate_container
from oos_validation.bundle import allowed_path
from oos_validation.result import RESULT_SCHEMA, validate_result


def _info():
    return {
        "Image": BASE_IMAGE,
        "Config": {"User": "65532:65532", "Labels": {"stock-agent.oos-validation.run": "0123456789abcdef"}},
        "HostConfig": {"NetworkMode": "none", "Privileged": False, "Binds": [], "PortBindings": {},
                        "ReadonlyRootfs": True, "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true"],
                        "Tmpfs": {"/tmp": "rw,nosuid,nodev,size=256m,mode=1777",
                                  "/results": "rw,nosuid,nodev,size=2m,uid=65532,gid=65532,mode=0700"}},
        "Mounts": [],
    }


def test_oos_launcher_is_networkless_and_has_no_host_mounts():
    args = create_args("0123456789abcdef", BASE_IMAGE)
    assert "--network" in args and args[args.index("--network") + 1] == "none"
    validate_container(_info(), "0123456789abcdef", BASE_IMAGE)
    bad = copy.deepcopy(_info())
    bad["Mounts"] = [{"Type": "bind", "Destination": "/work"}]
    with pytest.raises(ValueError, match="isolated_oos_container_rejected"):
        validate_container(bad, "0123456789abcdef", BASE_IMAGE)


def test_oos_result_is_fail_closed():
    good = {"schema": RESULT_SCHEMA, "status": "passed", "network": "none", "paths": "container-layer-only",
            "tests": {"passed": 10, "failed": 0}, "exit_code": 0, "cleanup_status": "removed"}
    assert validate_result(good)
    bad = {**good, "network": "host"}
    assert not validate_result(bad)


@pytest.mark.parametrize("path,allowed", [
    ("backend/oos_research/store.py", True),
    ("backend/.env", False),
    ("backend/cache/prod.sqlite3", False),
    ("tests/test_oos_research.py", True),
    ("../backend/api.py", False),
])
def test_oos_bundle_is_a_narrow_allowlist(path, allowed):
    assert allowed_path(path) is allowed
