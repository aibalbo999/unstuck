"""Offline TDD coverage for the disposable PostgreSQL validation launcher."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from pg_validation.bundle import allowed_path, build_context
from pg_validation.launcher import create_args, run_validation, validate_container


RUN_ID = "0123456789abcdef"
IMAGE_ID = "sha256:" + "a" * 64
CID = "b" * 64
TMPFS = {
    "/tmp": "rw,nosuid,nodev,size=768m,mode=1777",
    "/var/lib/postgresql/data": (
        "rw,nosuid,nodev,size=768m,uid=999,gid=999,mode=0700"
    ),
}


def _container_info() -> dict:
    return {
        "Id": CID,
        "Image": IMAGE_ID,
        "Config": {
            "User": "999:999",
            "Labels": {"stock-agent.validation.run": RUN_ID},
        },
        "HostConfig": {
            "NetworkMode": "none",
            "Privileged": False,
            "Binds": None,
            "PortBindings": {},
            "PublishAllPorts": False,
            "PidMode": "",
            "IpcMode": "private",
            "UTSMode": "",
            "UsernsMode": "",
            "CgroupnsMode": "private",
            "Devices": [],
            "DeviceRequests": [],
            "CapAdd": None,
            "CapDrop": ["ALL"],
            "SecurityOpt": ["no-new-privileges:true"],
            "Memory": 2 * 1024**3,
            "NanoCpus": 2 * 10**9,
            "PidsLimit": 256,
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
            "Tmpfs": dict(TMPFS),
        },
        "Mounts": [
            {"Type": "tmpfs", "Destination": "/tmp"},
            {"Type": "tmpfs", "Destination": "/var/lib/postgresql/data"},
        ],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        lambda info: info["HostConfig"].update(NetworkMode="host"),
        lambda info: info["HostConfig"].update(Privileged=True),
        lambda info: info["HostConfig"].update(Binds=["/host:/container"]),
        lambda info: info["HostConfig"].update(PortBindings={"5432/tcp": [{}]}),
        lambda info: info["HostConfig"].update(PublishAllPorts=True),
        lambda info: info["HostConfig"].update(PidMode="host"),
        lambda info: info["HostConfig"].update(IpcMode="host"),
        lambda info: info["HostConfig"].update(UTSMode="host"),
        lambda info: info["HostConfig"].update(UsernsMode="host"),
        lambda info: info["HostConfig"].update(CgroupnsMode="host"),
        lambda info: info.update(Image="sha256:" + "c" * 64),
        lambda info: info["Config"]["Labels"].update(
            {"stock-agent.validation.run": "fedcba9876543210"}
        ),
        lambda info: info["Config"].update(User="0:0"),
        lambda info: info["HostConfig"].pop("Memory"),
        lambda info: info["HostConfig"].pop("NanoCpus"),
        lambda info: info["HostConfig"].pop("PidsLimit"),
        lambda info: info["HostConfig"].update(Devices=[{"PathOnHost": "/dev/x"}]),
        lambda info: info["HostConfig"].update(
            DeviceRequests=[{"Driver": "", "Count": -1, "Capabilities": [["gpu"]]}]
        ),
        lambda info: info["HostConfig"].update(CapAdd=["SYS_ADMIN"]),
        lambda info: info["HostConfig"].pop("CapDrop"),
        lambda info: info["HostConfig"].update(CapDrop=None),
        lambda info: info["HostConfig"].update(CapDrop=["ALL", "NET_ADMIN"]),
        lambda info: info["HostConfig"].pop("SecurityOpt"),
        lambda info: info["HostConfig"].update(SecurityOpt=None),
        lambda info: info["HostConfig"].update(
            SecurityOpt=["no-new-privileges:true", "seccomp=unconfined"]
        ),
        lambda info: info["HostConfig"]["Tmpfs"].update({"/extra": "rw"}),
        lambda info: info["HostConfig"]["Tmpfs"].update({"/tmp": "rw"}),
        lambda info: info["Mounts"].append(
            {"Type": "volume", "Destination": "/anonymous"}
        ),
    ],
)
def test_validate_container_rejects_every_isolation_counterexample(mutation):
    info = _container_info()
    mutation(info)
    with pytest.raises(ValueError, match="^isolated_pg_container_rejected$") as exc:
        validate_container(info, RUN_ID, IMAGE_ID)
    assert IMAGE_ID not in str(exc.value)
    assert RUN_ID not in str(exc.value)


def test_validate_container_accepts_only_the_expected_isolated_shape():
    validate_container(_container_info(), RUN_ID, IMAGE_ID)


def test_create_args_is_the_exact_safe_container_argv():
    assert create_args(RUN_ID, IMAGE_ID) == [
        "docker",
        "create",
        "--name",
        f"stock-agent-pg-{RUN_ID}",
        "--label",
        f"stock-agent.validation.run={RUN_ID}",
        "--network",
        "none",
        "--ipc",
        "private",
        "--restart",
        "no",
        "--user",
        "999:999",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--cpus",
        "2",
        "--memory",
        "2g",
        "--pids-limit",
        "256",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=768m,mode=1777",
        "--tmpfs",
        (
            "/var/lib/postgresql/data:rw,nosuid,nodev,size=768m,"
            "uid=999,gid=999,mode=0700"
        ),
        IMAGE_ID,
        RUN_ID,
    ]


@pytest.mark.parametrize(
    "run_id,image_id",
    [
        ("short", IMAGE_ID),
        ("0123456789ABCDEf", IMAGE_ID),
        (RUN_ID, "postgres:latest"),
        (RUN_ID, "sha256:" + "A" * 64),
        (RUN_ID, "sha256:" + "a" * 63),
    ],
)
def test_create_args_rejects_untrusted_identifiers(run_id, image_id):
    with pytest.raises(ValueError):
        create_args(run_id, image_id)


@pytest.mark.parametrize(
    "name,expected",
    [
        ("backend/api.py", True),
        ("backend/requirements.lock", True),
        ("backend/model_routes.json", True),
        ("backend/templates/report.html", True),
        ("prompts/system.md", True),
        ("tests/test_something.py", True),
        ("tests/pg_validation/Dockerfile", True),
        ("tests/pg_validation/requirements.lock", True),
        ("backend/cache/prod.sqlite3", False),
        ("backend/output/report.html", False),
        ("backend/.env.production", False),
        ("tests/nested/test_hidden.py", False),
        ("../backend/api.py", False),
        ("/backend/api.py", False),
    ],
)
def test_allowed_path_is_a_narrow_explicit_allowlist(name, expected):
    assert allowed_path(name) is expected


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _mini_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    files = {
        "backend/api.py": b"SAFE = True\n",
        "backend/requirements.lock": b"psycopg==3.2.9\n",
        "backend/model_routes.json": b"{}\n",
        "backend/templates/report.html": b"safe\n",
        "prompts/system.md": b"safe\n",
        "tests/test_unit.py": b"def test_ok(): pass\n",
        "tests/pg_validation/Dockerfile": b"FROM scratch\n",
        "backend/cache/prod.sqlite3": b"secret-db",
        "backend/output/report.html": b"secret-output",
        ".env": b"PASSWORD=secret",
        "untracked.txt": b"not tracked",
    }
    for name, data in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    _git(
        repo,
        "add",
        "backend",
        "prompts",
        "tests",
        ".env",
    )
    return repo


def test_build_context_copies_only_allowed_tracked_files_and_hashes_manifest(tmp_path):
    repo = _mini_repo(tmp_path)
    destination = tmp_path / "context"
    manifest = build_context(repo, destination)
    copied = {entry["path"] for entry in manifest["files"]}
    assert copied == {
        "backend/api.py",
        "backend/model_routes.json",
        "backend/requirements.lock",
        "backend/templates/report.html",
        "prompts/system.md",
        "tests/pg_validation/Dockerfile",
        "tests/test_unit.py",
    }
    assert not (destination / ".env").exists()
    assert not (destination / "backend/cache/prod.sqlite3").exists()
    assert not (destination / "backend/output/report.html").exists()
    assert not (destination / ".git").exists()
    on_disk = json.loads((destination / "manifest.json").read_text())
    assert on_disk == manifest
    encoded_files = json.dumps(
        manifest["files"], sort_keys=True, separators=(",", ":")
    ).encode()
    assert manifest["manifest_sha256"] == hashlib.sha256(encoded_files).hexdigest()
    for entry in manifest["files"]:
        data = (destination / entry["path"]).read_bytes()
        assert entry == {
            "path": entry["path"],
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }


@pytest.mark.parametrize("replacement", ["symlink", "fifo"])
def test_build_context_rejects_tracked_non_regular_sources(tmp_path, replacement):
    repo = _mini_repo(tmp_path)
    victim = repo / "backend/api.py"
    victim.unlink()
    if replacement == "symlink":
        victim.symlink_to(repo / ".env")
    else:
        os.mkfifo(victim)
    with pytest.raises(ValueError, match="^isolated_pg_bundle_rejected$"):
        build_context(repo, tmp_path / "context")


def test_build_context_fails_closed_when_source_is_replaced_during_open(
    tmp_path, monkeypatch
):
    from pg_validation import bundle

    repo = _mini_repo(tmp_path)
    victim = repo / "backend/api.py"
    monkeypatch.setattr(bundle, "_index_paths", lambda _repo: ["backend/api.py"])
    real_open = bundle.os.open
    replaced = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal replaced
        name = os.fspath(path)
        opening_leaf = name == os.fspath(victim) or (
            name == "api.py" and "dir_fd" in kwargs
        )
        if not replaced and opening_leaf:
            replaced = True
            old = victim.with_suffix(".old")
            victim.rename(old)
            victim.write_bytes(b"EVIL = True\n")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(bundle.os, "open", racing_open)
    with pytest.raises(ValueError, match="^isolated_pg_bundle_rejected$"):
        build_context(repo, tmp_path / "context")


def test_build_context_fails_closed_when_source_stat_changes_after_read(
    tmp_path, monkeypatch
):
    from pg_validation import bundle

    repo = _mini_repo(tmp_path)
    victim = repo / "backend/api.py"
    monkeypatch.setattr(bundle, "_index_paths", lambda _repo: ["backend/api.py"])
    real_read = bundle.os.read
    changed = False

    def racing_read(fd, size):
        nonlocal changed
        data = real_read(fd, size)
        if data and not changed:
            changed = True
            victim.write_bytes(victim.read_bytes() + b"# changed\n")
        return data

    monkeypatch.setattr(bundle.os, "read", racing_read)
    with pytest.raises(ValueError, match="^isolated_pg_bundle_rejected$"):
        build_context(repo, tmp_path / "context")


def test_build_context_detects_same_size_rewrite_with_restored_mtime(
    tmp_path, monkeypatch
):
    from pg_validation import bundle

    repo = _mini_repo(tmp_path)
    victim = repo / "backend/api.py"
    monkeypatch.setattr(bundle, "_index_paths", lambda _repo: ["backend/api.py"])
    before = victim.stat()
    replacement = b"EVIL = True\n"
    assert len(replacement) == before.st_size
    real_read = bundle.os.read
    changed = False

    def racing_read(fd, size):
        nonlocal changed
        data = real_read(fd, size)
        if data and not changed:
            changed = True
            victim.write_bytes(replacement)
            os.utime(victim, ns=(before.st_atime_ns, before.st_mtime_ns))
        return data

    monkeypatch.setattr(bundle.os, "read", racing_read)
    with pytest.raises(ValueError, match="^isolated_pg_bundle_rejected$"):
        build_context(repo, tmp_path / "context")


def test_build_context_rejects_parent_replaced_by_external_symlink_during_open(
    tmp_path, monkeypatch
):
    from pg_validation import bundle

    repo = _mini_repo(tmp_path)
    victim = repo / "backend/api.py"
    external_parent = tmp_path / "moved-outside-repo"
    monkeypatch.setattr(bundle, "_index_paths", lambda _repo: ["backend/api.py"])
    real_open = bundle.os.open
    swapped = False

    def racing_open(path, flags, *args, **kwargs):
        nonlocal swapped
        name = os.fspath(path)
        opening_parent = name == "backend" and "dir_fd" in kwargs
        opening_old_leaf = name == os.fspath(victim)
        if not swapped and (opening_parent or opening_old_leaf):
            swapped = True
            victim.parent.rename(external_parent)
            victim.parent.symlink_to(external_parent, target_is_directory=True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(bundle.os, "open", racing_open)
    with pytest.raises(ValueError, match="^isolated_pg_bundle_rejected$"):
        build_context(repo, tmp_path / "context")
    assert swapped is True


@pytest.mark.parametrize("bad_destination", ["existing", "inside", "repo"])
def test_build_context_requires_a_new_destination_outside_repo(tmp_path, bad_destination):
    repo = _mini_repo(tmp_path)
    if bad_destination == "existing":
        destination = tmp_path / "existing"
        destination.mkdir()
    elif bad_destination == "inside":
        destination = repo / "context"
    else:
        destination = repo
    with pytest.raises(ValueError, match="^isolated_pg_bundle_rejected$"):
        build_context(repo, destination)


class FakeDocker:
    def __init__(self, mode: str = "success"):
        self.mode = mode
        self.calls: list[list[str]] = []
        self.kwargs: list[dict] = []
        self.run_id: str | None = None

    def __call__(self, argv, **kwargs):
        argv = list(argv)
        self.calls.append(argv)
        self.kwargs.append(kwargs)
        assert kwargs["check"] is True
        assert kwargs["text"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["shell"] is False
        assert kwargs["timeout"] <= 15 * 60
        assert set(kwargs["env"]) == {"DOCKER_HOST", "DOCKER_CONFIG", "PATH"}
        assert kwargs["env"]["DOCKER_HOST"].startswith("unix://")
        assert Path(kwargs["env"]["DOCKER_CONFIG"]).is_dir()
        command = argv[1]
        if command == "build":
            iidfile = Path(argv[argv.index("--iidfile") + 1])
            image_text = f" {IMAGE_ID} \n" if self.mode == "bad_image_id" else IMAGE_ID + "\n"
            iidfile.write_text(image_text)
            label = argv[argv.index("--label") + 1]
            self.run_id = label.rsplit("=", 1)[1]
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == "create":
            if "--cidfile" in argv and self.mode != "unrecoverable_create":
                cidfile = Path(argv[argv.index("--cidfile") + 1])
                cidfile.write_text(CID + "\n")
            if self.mode == "create_timeout":
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            malformed = self.mode in {"bad_cid", "unrecoverable_create"}
            cid_text = f" {CID} \n" if malformed else CID + "\n"
            return subprocess.CompletedProcess(argv, 0, cid_text, "")
        if command == "inspect":
            info = _container_info()
            info["Config"]["Labels"]["stock-agent.validation.run"] = self.run_id
            if self.mode == "inspect_rejection" and len(
                [call for call in self.calls if call[1] == "inspect"]
            ) == 1:
                info["HostConfig"]["NetworkMode"] = "host"
            return subprocess.CompletedProcess(argv, 0, json.dumps([info]), "")
        if command == "start":
            if self.mode == "start_failure":
                raise subprocess.CalledProcessError(1, argv, stderr="redacted")
            return subprocess.CompletedProcess(argv, 0, CID + "\n", "")
        if command == "wait":
            if self.mode == "wait_timeout":
                raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
            if self.mode == "keyboard_interrupt":
                raise KeyboardInterrupt
            exit_code = "7\n" if self.mode == "container_nonzero" else "0\n"
            return subprocess.CompletedProcess(argv, 0, exit_code, "")
        if command == "cp":
            destination = Path(argv[-1])
            if self.mode == "missing_result":
                return subprocess.CompletedProcess(argv, 0, "", "")
            if self.mode == "malformed_result":
                destination.write_text("not-json")
            else:
                destination.write_text('{"status":"passed"}\n')
            return subprocess.CompletedProcess(argv, 0, "", "")
        if command == "rm":
            if self.mode == "cleanup_failure":
                raise subprocess.CalledProcessError(1, argv, stderr="redacted")
            return subprocess.CompletedProcess(argv, 0, "", "")
        raise AssertionError(f"unexpected fake command: {argv}")


def _launcher_repo(tmp_path: Path) -> Path:
    return _mini_repo(tmp_path)


def _assert_no_start_before_validation(fake: FakeDocker):
    commands = [call[1] for call in fake.calls]
    starts = [index for index, command in enumerate(commands) if command == "start"]
    if starts:
        assert commands.index("inspect") < starts[0]


def _assert_cleanup_is_exact(fake: FakeDocker):
    removes = [call for call in fake.calls if call[1] == "rm"]
    for command in removes:
        assert command == ["docker", "rm", "-f", CID]


def test_run_validation_success_uses_fixed_commands_and_copies_valid_json(tmp_path):
    repo = _launcher_repo(tmp_path)
    result_dir = tmp_path / "result"
    fake = FakeDocker()
    assert run_validation(repo, result_dir, docker=fake) == 0
    assert json.loads((result_dir / "result.json").read_text()) == {"status": "passed"}
    _assert_no_start_before_validation(fake)
    _assert_cleanup_is_exact(fake)
    commands = [call[1] for call in fake.calls]
    assert commands == ["build", "create", "inspect", "start", "wait", "cp", "inspect", "rm"]
    build = fake.calls[0]
    assert build[:4] == ["docker", "build", "--platform", "linux/arm64"]
    create = next(call for call in fake.calls if call[1] == "create")
    forbidden = {"-p", "-P", "-v", "--volume", "--privileged"}
    assert not forbidden.intersection(create)


@pytest.mark.parametrize(
    "mode",
    [
        "inspect_rejection",
        "start_failure",
        "wait_timeout",
        "container_nonzero",
        "missing_result",
        "malformed_result",
        "keyboard_interrupt",
        "cleanup_failure",
        "bad_image_id",
        "create_timeout",
    ],
)
def test_run_validation_failure_states_are_nonzero_and_cleanup_only_exact_cid(
    tmp_path, mode
):
    repo = _launcher_repo(tmp_path)
    fake = FakeDocker(mode)
    assert run_validation(repo, tmp_path / "result", docker=fake) != 0
    _assert_no_start_before_validation(fake)
    _assert_cleanup_is_exact(fake)
    if mode == "inspect_rejection":
        assert all(call[1] != "start" for call in fake.calls)


def test_run_validation_recovers_malformed_create_stdout_from_controlled_cidfile(
    tmp_path,
):
    repo = _launcher_repo(tmp_path)
    fake = FakeDocker("bad_cid")
    assert run_validation(repo, tmp_path / "result", docker=fake) == 0
    _assert_cleanup_is_exact(fake)
    create = next(call for call in fake.calls if call[1] == "create")
    cidfile_index = create.index("--cidfile")
    assert cidfile_index > create.index("create")
    assert cidfile_index < create.index(IMAGE_ID)


def test_create_timeout_after_creation_recovers_cid_and_cleans_without_scanning(
    tmp_path,
):
    repo = _launcher_repo(tmp_path)
    fake = FakeDocker("create_timeout")
    assert run_validation(repo, tmp_path / "result", docker=fake) == 1
    _assert_cleanup_is_exact(fake)
    assert [call for call in fake.calls if call[1] == "inspect"] == [
        ["docker", "inspect", CID]
    ]
    assert [call for call in fake.calls if call[1] == "rm"] == [
        ["docker", "rm", "-f", CID]
    ]
    assert all(call[1] != "start" for call in fake.calls)


def test_unrecoverable_create_identity_returns_cleanup_failed_without_scanning(
    tmp_path,
):
    repo = _launcher_repo(tmp_path)
    fake = FakeDocker("unrecoverable_create")
    assert run_validation(repo, tmp_path / "result", docker=fake) == 2
    commands = [call[1] for call in fake.calls]
    assert "inspect" not in commands
    assert "rm" not in commands
    assert "ps" not in commands


def test_run_validation_does_not_delete_when_cleanup_identity_label_mismatches(tmp_path):
    repo = _launcher_repo(tmp_path)

    class LabelMismatchDocker(FakeDocker):
        def __call__(self, argv, **kwargs):
            result = super().__call__(argv, **kwargs)
            inspect_count = sum(call[1] == "inspect" for call in self.calls)
            if list(argv)[1] == "inspect" and inspect_count == 2:
                info = json.loads(result.stdout)
                info[0]["Config"]["Labels"]["stock-agent.validation.run"] = "bad"
                return subprocess.CompletedProcess(argv, 0, json.dumps(info), "")
            return result

    fake = LabelMismatchDocker()
    assert run_validation(repo, tmp_path / "result", docker=fake) != 0
    assert all(call[1] != "rm" for call in fake.calls)


@pytest.mark.parametrize("kind", ["existing", "cache", "output", "repo", "symlink"])
def test_run_validation_rejects_unsafe_result_directories_before_docker(tmp_path, kind):
    repo = _launcher_repo(tmp_path)
    if kind == "existing":
        result = tmp_path / "result"
        result.mkdir()
    elif kind in {"cache", "output"}:
        parent = tmp_path / kind
        parent.mkdir()
        result = parent / "result"
    elif kind == "repo":
        result = repo
    else:
        target = tmp_path / "target"
        target.mkdir()
        result = tmp_path / "result"
        result.symlink_to(target)
    fake = FakeDocker()
    assert run_validation(repo, result, docker=fake) != 0
    assert fake.calls == []
