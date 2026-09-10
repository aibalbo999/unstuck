# PostgreSQL 隔離驗證 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不碰正式 runtime／資料／憑證的拋棄式環境，以真 PostgreSQL 驗證 checkpoint 與 quality draft 的保存、恢復及故障阻擋。

**Architecture:** 使用同容器 PostgreSQL＋Python、Unix socket、network=none。主機工具只建立白名單程式副本、檢查精確容器設定及匯出非敏感結果；測試重用既有真 workflow 與 deterministic 模型 fixtures。原 SQLite 測試保留，PG live suite 明確 opt-in 且缺案例／skip 不算通過。

**Tech Stack:** Python 3.13、PostgreSQL 17.11、LangGraph 1.2.6、checkpoint-postgres 3.1.0、psycopg binary 3.3.4、pytest 9.0.3、Docker linux/arm64。

---

狀態（2026-09-10 同步）：**Task 1～9、真實 PostgreSQL image build、live
PG-00～08 與精確 cleanup 均已完成。正式驗收為 17/17 cases、51/51 phases、
`status=passed`、`server_stop_status=stopped`、`cleanup_status=removed`。**
這只完成隔離驗證，不代表正式 runtime 已切換至 PostgreSQL。設計來源：[PG 規格](../specs/2026-09-06-postgres-isolated-verification-design.md)。
OOS 後續已依獨立計畫完成工程與收樣啟用，仍不屬於本 PG 計畫的驗收範圍。

## 執行邊界與命令約定

- 目前 checkout：`/Volumes/X10 Pro Mac/stock-agent`；app 舊 Desktop 路徑不存在，不使用它執行命令。
- 起點：`ea6023bc` 的已審閱設計，程式基準為 `fec17737`。開始實作依 `using-git-worktrees` 建立隔離工作樹；主機 `.venv` 只當 Python executable，不安裝套件或複製進 image。
- 所有以下 shell 命令在**實作工作樹根目錄**執行，`python` 指 `/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python`。啟動工具以自己的 `__file__` 找工作樹，不回退正式 checkout。
- 一般測試命令固定使用 `python -B tests/run_prompt_boundary_tests.py` 作入口，附 task 指定測試檔與 `-q -p no:cacheprovider --tb=short`，不得裸 pytest。
- 只允許本次建立的容器、image 與暫存資料；不 push、merge、重啟正式服務、改 `.env`／`.venv`、建正式 DB／schema、enqueue 或重建歷史報告。
- 下列程式區塊是實作單元與測試內容；引用現有 fixture／函式時保留其正文與斷言，不用重新杜撰簡化 workflow。每個 task 完成後先測試再局部 commit。

## 固定環境與可驗證來源

| 項目 | 固定值 |
| --- | --- |
| base image | `postgres:17.11-trixie@sha256:413da4542e091471785b7f18f1a2258df134bc6506ab4e1e53725aa8bcfdb650` |
| platform | `linux/arm64` |
| PG package | `17.11-1.pgdg13+2` |
| Python／venv apt | `3.13.5-2+deb13u3` |
| Python dependencies | 現有 `backend/requirements.lock` 全部 pins／hashes，加獨立 binary distribution lock |
| binary wheel SHA-256 | `26df2717e59c0473e4465a97dfb1b7afebaa479277870fd5784d1436470db47c` |

image digest 已以官方 registry metadata 查核；不是派生測試 image 的 ID。派生 image 必須建置後保存實際 ID。PG base 宣告 `/var/lib/postgresql/data` volume，並把預設 listener 設為 `*`；本計畫明確覆蓋這兩項。[官方 image metadata](https://raw.githubusercontent.com/docker-library/repo-info/master/repos/postgres/remote/17.11-trixie.md)

Python apt 版本與 arm64 支援見 [Debian Python](https://packages.debian.org/trixie/python3.13)、[Debian venv](https://packages.debian.org/trixie/python3.13-venv)。指定版本取得失敗即停止準備，不自動改版本。binary wheel 是 cp313 Linux aarch64，見 [PyPI 發佈 metadata](https://pypi.org/pypi/psycopg-binary/3.3.4/json)。設 `PSYCOPG_IMPL=binary`，實際 libpq 版本由測試 image 回報，不推定等於 server。[Psycopg 官方說明](https://www.psycopg.org/psycopg3/docs/basic/install.html)

## 檔案責任與交付順序

| 檔案 | 動作／責任 |
| --- | --- |
| `tests/pg_validation/__init__.py` | 新增空 package marker |
| `tests/pg_validation/policy.py` | 純 conninfo／run identity／容器 inspect 判定 |
| `tests/pg_validation/guard.py` | pytest 前安裝 psycopg 同步／非同步 guard |
| `tests/pg_validation/bundle.py` | 白名單檔案選取、hash、受限 build context |
| `tests/pg_validation/launcher.py` | 建置／create／inspect／start／wait／匯出／精確 cleanup |
| `tests/pg_validation/entrypoint.py` | 非 root 建 PG cluster／角色，啟動既有 runner |
| `tests/pg_validation/cases.py` | 真 PG fixture、draft reader、權限 barrier、結果記錄 |
| `tests/pg_validation/Dockerfile` | 固定 image／套件、不含正式資料 |
| `tests/pg_validation/binary.lock` | 只補 psycopg-binary wheel，不改正式 lock |
| `scripts/run_postgres_validation.py` | 薄 CLI，無任意 DSN、volume 或 Docker options 入口 |
| `tests/run_prompt_boundary_tests.py` | 明確設定 output／checkpoint backend、安裝 guard 與 live 結果插件 |
| `tests/workflow_quality_draft_test_support.py` | 從 SQLite 測試原樣抽出共用 fixtures／builder |
| `tests/test_workflow_quality_draft_resume.py` | 只改共用 fixture imports，保留 SQLite SQL 與測試斷言 |
| `tests/test_postgres_validation_policy.py` | 無 DB／Docker 的輸入與邊界反例 |
| `tests/test_postgres_validation_launcher.py` | fake process adapter 的生命週期／清理反例 |
| `tests/test_workflow_postgres_live.py` | PG-01～08 真實測試，不取代既有 SQLite suite |
| `docs/postgres-isolated-verification.md` | 操作手冊、結果界線、清理失敗處理 |
| `docs/postgres-isolated-verification-delivery-2026-09-06.md` | 執行後才填實際結果，不預填 passed |

Task 1／2 可由不同 implementer 分工；Task 3 依賴兩者，Task 4～7 在隔離工具完成後進行。主 agent 自己核對每個規格 ID 的證據；不以 agent 的「完成」代替實際輸出。

### Task 1：純連線政策與預設拒絕

**Files:** Create `tests/pg_validation/{__init__,policy,guard}.py`、`tests/test_postgres_validation_policy.py`；Modify `tests/run_prompt_boundary_tests.py`。

- [x] **Step 1：先寫 conninfo 邊界測試。** `Endpoint` 是固定值物件，不接受 URI／kwargs 覆寫 endpoint；錯誤只回穩定原因，不回傳輸入 conninfo。

```python
import pytest
from pg_validation.policy import Endpoint

def endpoint():
    return Endpoint("/tmp/pg-validation-0123456789abcdef/socket", "5432",
                    "db_0123456789abcdef", "app_0123456789abcdef")

@pytest.mark.parametrize("suffix", [
    " hostaddr=127.0.0.1", " service=production", " host=other",
    " options=-csearch_path=public", " port=5433", " dbname=other",
    " user=postgres", " host=/tmp/other", " connect_timeout=0",
])
def test_rejects_connection_overrides(suffix):
    with pytest.raises(ValueError, match="isolated_pg_connection_rejected"):
        endpoint().validate(endpoint().conninfo() + suffix, {})

def test_requires_every_identity_field_without_defaults():
    with pytest.raises(ValueError):
        endpoint().validate("dbname=db_0123456789abcdef", {})
    with pytest.raises(ValueError):
        endpoint().validate("postgresql://localhost/test", {})
    endpoint().validate(endpoint().conninfo(), {"autocommit": True})

def test_kwargs_cannot_override_conninfo():
    with pytest.raises(ValueError):
        endpoint().validate(endpoint().conninfo(), {"hostaddr": "127.0.0.1"})
```

- [x] **Step 2：跑紅燈。** `python -B tests/run_prompt_boundary_tests.py tests/test_postgres_validation_policy.py -q -p no:cacheprovider --tb=short`；預期新 module 尚未存在造成 collection failure，記錄原因，不能把其他錯誤算本案例紅燈。
- [x] **Step 3：新增 `policy.py` 的 conninfo 單元。** 只接受固定、安全 token；本測試環境採同 UID、0700 socket 的 local trust，沒有可外傳的密碼，管理角色只由 fixture 注入。這不是正式 PG 的認證建議。

```python
from dataclasses import dataclass
import re

CLIENT_OPTIONS = {"autocommit", "row_factory", "cursor_factory",
                  "prepare_threshold", "context"}

@dataclass(frozen=True)
class Endpoint:
    host: str
    port: str
    dbname: str
    user: str

    def values(self):
        if not re.fullmatch(r"/tmp/pg-validation-[0-9a-f]{16}/socket", self.host):
            raise ValueError("isolated_pg_identity_invalid")
        run = self.host.split("/")[2].removeprefix("pg-validation-")
        if (self.port != "5432" or self.dbname != f"db_{run}"
                or self.user not in {f"app_{run}", f"owner_{run}"}):
            raise ValueError("isolated_pg_identity_invalid")
        return {"host": self.host, "port": self.port, "dbname": self.dbname,
                "user": self.user, "connect_timeout": "5", "sslmode": "disable"}

    def conninfo(self):
        return " ".join(f"{key}={value}" for key, value in self.values().items())

    def validate(self, conninfo, kwargs):
        failure = ValueError("isolated_pg_connection_rejected")
        if not isinstance(conninfo, str) or not set(kwargs) <= CLIENT_OPTIONS:
            raise failure
        pairs = [token.split("=", 1) for token in conninfo.split()]
        if (any(len(pair) != 2 for pair in pairs)
                or len({pair[0] for pair in pairs}) != len(pairs)
                or dict(pairs) != self.values()):
            raise failure
```

- [x] **Step 4：新增 guard 並用 fake driver 驗證同步、非同步、top-level alias 在真正 connect 前遭拒。** `guard.py` 接受已載入的 driver 與本次兩個 Endpoint；沒有 policy 時全部拒絕。不可在 guard 中連線測試可用性。

```python
def install(driver, endpoints=()):
    sync_connect = driver.Connection.connect.__func__
    async_connect = driver.AsyncConnection.connect.__func__

    def check(conninfo, kwargs):
        for endpoint in endpoints:
            try:
                endpoint.validate(conninfo, kwargs)
                return
            except ValueError:
                pass
        raise ValueError("isolated_pg_connection_rejected")

    def checked_sync(cls, conninfo="", **kwargs):
        check(conninfo, kwargs)
        return sync_connect(cls, conninfo, **kwargs)

    async def checked_async(cls, conninfo="", **kwargs):
        check(conninfo, kwargs)
        return await async_connect(cls, conninfo, **kwargs)

    driver.Connection.connect = classmethod(checked_sync)
    driver.AsyncConnection.connect = classmethod(checked_async)
    driver.connect = driver.Connection.connect
```

Fake driver 測試內容：三個入口使用計數器；沒有 policy／惡意 DSN 時 counter=0；合法 owner／app DSN 各通過一次。另保存 `alias = driver.connect`（安裝 guard 後取得），證明 alias 同樣受限；guard 必須在 pytest／業務 imports 前安裝，不允許先取得原始 alias 再使用。

- [x] **Step 5：保留 runner 現有 SQLite 與 socket guard，增加明確設定。** 在既有 `os.environ.update` 增加以下內容；live endpoint 載入與插件在 Task 3 定義後接入，預設 PG 保持拒絕。

```python
"OUTPUT_DIR": str(root / "output"),
"LANGGRAPH_CHECKPOINT_BACKEND": "sqlite",
"LANGGRAPH_CHECKPOINT_POSTGRES_DSN": "isolated-postgres-disabled",
```

容器副本不存在 `.env`。主機一般 runner 的非空 disabled DSN 防止 `.env` 回填且所有 PG guard 預設拒絕；不能宣稱主機 Python patch 封鎖任意 native C 呼叫。測試自建 `.env` 的 env-loading 回歸仍要保留，不全域改掉 production loader。

- [x] **Step 6：跑綠燈與 runtime/storage 回歸。** 命令包含 `tests/test_postgres_validation_policy.py tests/test_runtime_paths.py tests/test_settings_env_loading.py tests/test_storage_inventory.py tests/test_report_artifacts.py`，全部經隔離 runner。預期無失敗；另加入 `PGHOSTADDR`／`PGSERVICE` 不影響固定 DSN 的反例。
- [x] **Step 7：局部 commit。** `git add tests/pg_validation/__init__.py tests/pg_validation/policy.py tests/pg_validation/guard.py tests/test_postgres_validation_policy.py tests/run_prompt_boundary_tests.py`；`git commit -m "test: enforce explicit PostgreSQL isolation policy"`。

### Task 2：白名單 context、Docker 設定與清理狀態機

**Files:** Create `tests/pg_validation/bundle.py`、`tests/pg_validation/launcher.py`、`scripts/run_postgres_validation.py`、`tests/test_postgres_validation_launcher.py`；Modify `tests/pg_validation/policy.py`。

- [x] **Step 1：先寫純容器設定反例。** 測試參數逐一包含 network=host、privileged、bind mount、anonymous volume、port binding、host PID／IPC、錯 image／run label、缺 CPU／memory／PIDs limit；都必須在 fake `start` 前失敗。

```python
def validate_container(info, *, run_id, image_id):
    h = info["HostConfig"]
    c = info["Config"]
    valid = (
        info["Image"] == image_id
        and c.get("User") == "999:999"
        and c.get("Labels", {}).get("stock-agent.validation.run") == run_id
        and h.get("NetworkMode") == "none"
        and not h.get("Privileged") and not h.get("Binds")
        and not h.get("PortBindings") and not h.get("PublishAllPorts")
        and h.get("PidMode", "") == ""
        and h.get("IpcMode") == "private"
        and not h.get("Devices") and not h.get("CapAdd")
        and h.get("Memory") == 2 * 1024 ** 3
        and h.get("NanoCpus") == 2 * 10 ** 9
        and h.get("PidsLimit") == 256
        and h.get("RestartPolicy", {}).get("Name") == "no"
        and set(h.get("Tmpfs", {})) == {"/tmp", "/var/lib/postgresql/data"}
        and all(m.get("Type") == "tmpfs" for m in info.get("Mounts", []))
    )
    if not valid:
        raise ValueError("isolated_pg_container_rejected")
```

- [x] **Step 2：跑紅燈。** `python -B tests/run_prompt_boundary_tests.py tests/test_postgres_validation_launcher.py -q -p no:cacheprovider --tb=short`；預期缺新 validate／launcher 實作，不接觸 Docker。
- [x] **Step 3：新增白名單 builder。** 來源由目前工作樹 `git ls-files -z` 的已追蹤／已 staged 路徑取得，不掃正式 output；對每份允許檔案以 `lstat` 拒絕 symlink／非一般檔，再讀 bytes 計 hash 和複製。`bundle.py` 的選取規則如下，產生逐檔 `{path, sha256, size}` manifest，並把該 manifest hash 傳給派生 image label。

```python
from pathlib import PurePosixPath

EXACT = {"backend/requirements.lock", "backend/model_routes.json"}
DENIED = {"cache", "output", ".git", ".venv", "__pycache__"}

def allowed_path(name):
    p = PurePosixPath(name)
    if (not p.parts or p.is_absolute() or ".." in p.parts or set(p.parts) & DENIED
            or any(part.startswith(".env") for part in p.parts)):
        return False
    if name in EXACT:
        return True
    if p.parts[0] == "backend" and p.suffix == ".py":
        return True
    if name.startswith("backend/templates/") and p.suffix in {".j2", ".html"}:
        return True
    if p.parts[0] == "prompts" and p.suffix in {".md", ".json", ".yaml"}:
        return True
    if name.startswith("tests/pg_validation/"):
        return p.suffix in {".py", ".lock"} or p.name == "Dockerfile"
    return p.parts[0] == "tests" and len(p.parts) == 2 and p.suffix == ".py"
```

`build_context` 的完整寫入單元如下；只用於本次 TemporaryDirectory，不編輯正式檔案。測試建立含 `.env`、fake DB、fake artifact、symlink、FIFO 的迷你 repo，assert 禁止內容／連結未進 manifest；允許檔案遭替換或讀取前後 stat 改變則 fail closed。禁止 `COPY . .` 搭配原 repo context。

```python
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

def build_context(repo: Path, destination: Path) -> dict:
    repo = repo.resolve(strict=True)
    destination = destination.resolve(strict=False)
    if destination.exists() or destination.is_relative_to(repo):
        raise ValueError("isolated_context_destination_rejected")
    names = subprocess.run(["git", "ls-files", "-z"], cwd=repo,
                           capture_output=True, check=True).stdout.decode().split("\0")
    selected = []
    for name in sorted(filter(None, names)):
        if not allowed_path(name):
            continue
        source = repo / name
        if any(parent.is_symlink() for parent in (source, *source.parents) if parent != repo):
            raise ValueError("isolated_context_symlink_rejected")
        before = source.lstat()
        if not stat.S_ISREG(before.st_mode) or not source.resolve().is_relative_to(repo):
            raise ValueError("isolated_context_source_rejected")
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            opened = os.fstat(stream.fileno())
            payload = stream.read()
            after = os.fstat(stream.fileno())
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
        if not (signature(before) == signature(opened) == signature(after)
                == signature(source.lstat())):
            raise ValueError("isolated_context_source_changed")
        selected.append((name, payload))
    destination.mkdir(mode=0o700)
    files = []
    for name, payload in selected:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload)
        files.append({"path": name, "size": len(payload),
                      "sha256": hashlib.sha256(payload).hexdigest()})
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    manifest = {"files": files, "sha256": hashlib.sha256(encoded).hexdigest()}
    with (destination / "manifest.json").open("x") as stream:
        json.dump(manifest, stream, sort_keys=True)
    return manifest
```

- [x] **Step 4：新增 Docker create argv builder。** 對 run ID 用 `[0-9a-f]{16}`，image ID 用 `sha256:[0-9a-f]{64}` 嚴格驗證。`EXPOSE 5432` 不是 binding，不因它而放行 `-P`。

```python
def create_args(run_id, image_id):
    import re
    if not re.fullmatch(r"[0-9a-f]{16}", run_id):
        raise ValueError("invalid_run_id")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise ValueError("invalid_image_id")
    return [
        "docker", "create", "--name", f"stock-agent-pg-{run_id}",
        "--label", f"stock-agent.validation.run={run_id}",
        "--network", "none", "--ipc", "private", "--restart", "no",
        "--user", "999:999", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges:true",
        "--cpus", "2", "--memory", "2g", "--pids-limit", "256",
        "--tmpfs", "/tmp:rw,nosuid,nodev,size=768m,mode=1777",
        "--tmpfs", "/var/lib/postgresql/data:rw,nosuid,nodev,size=768m,uid=999,gid=999,mode=0700",
        image_id, run_id,
    ]
```

- [x] **Step 5：新增受限 launcher 流程與 fake process 測試。** 公開 `run_validation(repo: Path, result_dir: Path, *, docker=subprocess.run) -> int`，CLI 只有必填 `--result-dir`；result_dir 必須不存在，父目錄不是正式 cache/output，禁止 symlink／repo root。每次用 `secrets.token_hex(8)` 新 run ID，不接受外部 container 名稱、DSN 或任意 Docker flags。

依序使用以下 argv；`docker` adapter 呼叫固定 `check=True, text=True, capture_output=True`，不得 `shell=True`，每個指令有 timeout。先以唯讀 Docker context inspect 解出本機 Unix socket，拒絕 tcp／ssh／remote daemon；後續明確指定該 host 與本次空 Docker config directory，避免 Docker 自動把主機 proxy／registry 設定帶進 build。build stdout／stderr 只留本次受限準備紀錄，不向 console 輸出環境；image ID 嚴格解析再使用。

```python
["docker", "version", "--format", "{{.Server.Version}}"]
["docker", "build", "--platform", "linux/arm64", "--iidfile", str(iidfile),
 "--label", f"stock-agent.validation.run={run_id}",
 "-f", str(context / "tests/pg_validation/Dockerfile"), str(context)]
create_args(run_id, image_id)
["docker", "inspect", container_id]
["docker", "start", container_id]
["docker", "wait", container_id]
["docker", "cp", f"{container_id}:/results/result.json", str(result_file)]
["docker", "rm", "-f", container_id]
```

先 create（不執行 entrypoint），取回完整 64 hex container ID；inspect 通過才 start。build 最多 15 分鐘，agent 等待時每次 tool yield 不超過 60 秒；驗證容器最多 10 分鐘。`wait` 回傳的 container exit code 不是 docker CLI exit code，需獨立解析。以 `try/finally` 清理已記錄的精確 ID；create 回應不明時只讀 `--cidfile` 或 inspect 精確本次名稱／label 解析 ID，不以 prefix 掃描所有資源。

cleanup 前再核對 ID 與 run label；不符則回 `cleanup_failed` 並停止刪除。不刪其他 container／volume／image，不 `prune`。沒有 anonymous volume 才可開始；因此不需要清理任何共享 volume。派生 image 保留作快取並在 delivery 明示。

fake process 測試涵蓋成功、inspect 拒絕、start 失敗、wait timeout、非零 container exit、缺 result、異常 result、KeyboardInterrupt 與 cleanup 失敗；每一例 assert 只傳精確本次 ID，且非成功／未清理狀態不回 0。

- [x] **Step 6：跑綠燈並提交。** 先兩個新增 offline test files；再 `git diff --check`。局部提交上述 files，commit message：`test: add disposable PostgreSQL container boundary`。此 task 仍不執行 live suite。

### Task 3：固定 image 與非 root PG bootstrap

**Files:** Create `tests/pg_validation/{Dockerfile,binary.lock,entrypoint.py}`；接入 `guard.py`／runner 的 live policy。

- [x] **Step 1：新增 image contract 測試。** 斷言固定 base digest、apt versions、`USER 999:999`、binary implementation、無原 repo context、覆蓋官方 entrypoint；entrypoint argv 測試確認 `listen_addresses=''`、0700 socket、readiness timeout，且沒有 host/port publication。
- [x] **Step 2：跑紅燈後新增 image 與 binary lock。** 不重新 resolve 正式 lock。

```dockerfile
FROM --platform=linux/arm64 postgres:17.11-trixie@sha256:413da4542e091471785b7f18f1a2258df134bc6506ab4e1e53725aa8bcfdb650
USER root
RUN apt-get update && apt-get install -y --no-install-recommends python3.13=3.13.5-2+deb13u3 python3.13-venv=3.13.5-2+deb13u3 && python3.13 -m venv /opt/pg-test-venv
COPY backend/requirements.lock /opt/locks/backend.lock
COPY tests/pg_validation/binary.lock /opt/locks/binary.lock
RUN /opt/pg-test-venv/bin/python -m pip install --require-hashes -r /opt/locks/backend.lock -r /opt/locks/binary.lock
COPY backend /work/backend
COPY tests /work/tests
COPY prompts /work/prompts
COPY manifest.json /opt/validation-manifest.json
RUN install -d -o 999 -g 999 -m 0700 /results
ENV PATH="/opt/pg-test-venv/bin:${PATH}" PYTHONPATH="/work/tests:/work/backend" PYTHONDONTWRITEBYTECODE=1 PSYCOPG_IMPL=binary
USER 999:999
WORKDIR /work
ENTRYPOINT ["/opt/pg-test-venv/bin/python", "-B", "-m", "pg_validation.entrypoint"]
```

```text
psycopg-binary==3.3.4 --hash=sha256:26df2717e59c0473e4465a97dfb1b7afebaa479277870fd5784d1436470db47c
```

`backend/requirements.lock` 可能含無適配 wheel 的 transitive package；安裝或 hash 驗證失敗是 preparation failure，不關掉 `--require-hashes`、不改正式 lock、不自動改依賴版本。只有確認必要、固定版本的建置依賴才可局部補 image，並重新記錄派生 image ID。

- [x] **Step 3：實作 bootstrap 的固定身份與程序。** run ID 由唯一命令列參數取得，驗證 16 hex；使用 `Endpoint` 產生 owner／app 字串，不讀主機環境 DSN。先用白名單環境啟動 child，不沿用 `PG*`、provider keys、proxy／service file。root 的值是 task-specific Path，不改 HOME／CODEX_HOME。

```python
root = Path(f"/tmp/pg-validation-{run_id}")
root.mkdir(mode=0o700)
socket_dir = root / "socket"
socket_dir.mkdir(mode=0o700)
data_dir = Path("/var/lib/postgresql/data") / run_id
owner = f"owner_{run_id}"
app = f"app_{run_id}"
database = f"db_{run_id}"
child_env = {
    "PATH": os.environ["PATH"], "LANG": "C.UTF-8",
    "PYTHONPATH": "/work/tests:/work/backend",
    "PYTHONDONTWRITEBYTECODE": "1", "PSYCOPG_IMPL": "binary",
}
subprocess.run(["initdb", "-D", str(data_dir), "-U", owner,
                "--auth-local=trust", "--auth-host=reject", "--no-locale"],
               env=child_env, check=True, capture_output=True, timeout=60)
subprocess.run(["pg_ctl", "-D", str(data_dir), "-l", str(root / "postgres.log"),
                "-o", f"-k {socket_dir} -p 5432 -c listen_addresses=''",
                "-w", "-t", "60", "start"],
               env=child_env, check=True, capture_output=True, timeout=65)
```

以顯式 `psql -h <socket> -p 5432 -U <owner> -d postgres` 的 `stdin` 執行建立 app role 與 dedicated DB，command text 不含密碼；role／DB 名稱先通過生成 token 限制，SQL identifiers 用 `psycopg.sql.Identifier` 或固定受限字元組合，不拼外來 SQL。app 固定 `LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION`。cluster 只有本次測試資料。

這裡只建立空 dedicated DB／roles，不先建立 saver tables。Task 4 的 session fixture 才以 owner 首次 `AsyncPostgresSaver.setup()`，保存實際 setup 前後觀測供 PG-01 驗證；其他案例共享已遷移的 dedicated DB，使用唯一 thread identity 避免 test-order 依賴。

- [x] **Step 4：寫只供本次容器的 policy file，接入 runner。** policy 包含 run ID、owner/app Endpoint、input manifest hash，檔案 0600，位於 `root / "policy.json"`；不含憑證。runner live opt-in 固定環境變數 `STOCK_AGENT_PG_VALIDATION_POLICY`，不接受普通 production DSN。

loader 必須驗證 Linux、`/.dockerenv`、精確 `/tmp/pg-validation-<run>/policy.json` 路徑、無 symlink、檔案 uid=目前非 root uid、run ID 一致與固定 endpoint 形狀；不符即 nonzero。這是誤用防護，不是宣稱檔案旗標能取代 Docker inspect。

在 pytest import 前清理 inherited `PG*` 並安裝 `guard.install(psycopg, (owner_endpoint, app_endpoint))`；無 policy 時若 psycopg 可 import，安裝預設全拒 guard；無 policy 且 driver import 不可用保留 offline 測試可執行。指定 live policy 但 driver import 失敗必須 nonzero。

entrypoint child 呼叫：

```python
subprocess.run([
    sys.executable, "-B", "tests/run_prompt_boundary_tests.py",
    "tests/test_workflow_postgres_live.py", "-q", "-p", "no:cacheprovider",
    "--tb=short",
], env={**child_env, "STOCK_AGENT_PG_VALIDATION_POLICY": str(policy_file)},
   cwd="/work", timeout=600, capture_output=True, text=True)
```

stdout／stderr 只留容器內本次私有 log，不直接匯出；主機只取插件產生的 structured result。entrypoint 成功／失敗／中斷都在 finally `pg_ctl -D <exact data_dir> -w -t 30 stop`；停止失敗需記錄，不能覆蓋成成功。不可 `--rm` 自動移除後才取結果。

- [x] **Step 5：完成 unit 綠燈，再首次準備 image。** 已建置並驗證派生 image `sha256:9816a7d97b354827d9bc281974a8b90d81b1733d630657256499677cd601ec3a`；實際 runtime 為 Python 3.13.5、PostgreSQL 17.11、psycopg 3.3.4、libpq 180000、saver 3.1.0 與 binary implementation。
- [x] **Step 6：提交 image／bootstrap／runner scoped changes。** commit message：`test: provision pinned offline PostgreSQL runtime`。若 PG readiness 或 driver 不可用，只回報 preparation failure，不進 PG 成功結論。

### Task 4：共用 fixtures 與真 PG 讀寫 helper

**Files:** Create `tests/workflow_quality_draft_test_support.py`、`tests/pg_validation/cases.py`、`tests/test_workflow_postgres_live.py`；Modify `tests/test_workflow_quality_draft_resume.py`。

- [x] **Step 1：先記錄 SQLite 基線。** 跑 `tests/test_workflow_quality_draft_resume.py tests/test_workflow_checkpoint_resume.py tests/test_workflow_quality_draft_cold_imports.py tests/test_repair_dependencies.py`，確認全部從隔離 runner 執行且無失敗。
- [x] **Step 2：純搬移共用 fixtures。** 從 `tests/test_workflow_quality_draft_resume.py` 原樣移出 `initial_state`、`quality_runtime`、`builder_for`、`intermediate_quality_runtime` 四個符號與其 imports 到 support file，保留 decorators；不改生成／品質斷言。SQLite 檔仍保留 `execute`、`draft_records`、`main_snapshot` 與全部 test bodies。

```python
from workflow_quality_draft_test_support import (
    initial_state, quality_runtime, builder_for, intermediate_quality_runtime,
)
```

再次執行 Step 1 同命令，測試收集數與行為須相同，才提交這個純測試重構：`test: share deterministic workflow draft fixtures`。

- [x] **Step 3：新增真 PG helper，禁止重用 SQLite serializer／SQL。** `PgCase` 的 Endpoint 只來自 runner 已驗證 policy；每個 test 另取 UUID 作 thread prefix，資料留本次 DB 到容器清理，不 truncate 共用或正式表。

```python
import asyncio
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from workflow_checkpoints import execute_persistent_graph, open_postgres_checkpointer
from workflow_quality_draft_test_support import builder_for

@dataclass
class PgCase:
    app_endpoint: object
    owner_endpoint: object
    sqlite_path: Path
    prefix: str

    def thread(self, name="draft-job"):
        return f"{self.prefix}:{name}"

    def execute(self, state, calls, *, thread="draft-job", agents=(4,), builder=None):
        return asyncio.run(execute_persistent_graph(
            graph_builder=builder if builder is not None else builder_for(calls, agents),
            initial_state=state, thread_id=self.thread(thread),
            checkpoint_path=self.sqlite_path, checkpoint_backend="postgres",
            checkpoint_postgres_dsn=self.app_endpoint.conninfo(),
        ))

    def tuples(self, thread="draft-job"):
        async def read():
            async with open_postgres_checkpointer(self.app_endpoint.conninfo()) as saver:
                config = {"configurable": {"thread_id": self.thread(thread)}}
                return sorted([item async for item in saver.alist(config)],
                              key=lambda item: item.checkpoint["id"])
        return asyncio.run(read())

    def drafts(self, thread="draft-job"):
        return [item for item in self.tuples(thread)
                if item.config["configurable"].get("checkpoint_ns", "").startswith("quality_draft/")]

    def snapshot(self, calls, *, thread="draft-job", agents=(4,), builder=None):
        async def read():
            async with open_postgres_checkpointer(self.app_endpoint.conninfo()) as saver:
                graph_builder = builder if builder is not None else builder_for(calls, agents)
                graph = graph_builder.compile(checkpointer=saver)
                return await graph.aget_state({"configurable": {
                    "thread_id": self.thread(thread), "checkpoint_ns": ""}})
        return asyncio.run(read())

    async def permissions(self, enabled):
        import psycopg
        from psycopg import sql
        action, direction = ("GRANT", "TO") if enabled else ("REVOKE", "FROM")
        query = sql.SQL(action + " INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
                        + direction + " {}").format(sql.Identifier(self.app_endpoint.user))
        async with await psycopg.AsyncConnection.connect(
                self.owner_endpoint.conninfo(), autocommit=True) as conn:
            await conn.execute(query)
```

session fixture 先查 `pg_tables` 證明專用 public schema 原本沒有 saver tables，保存原始觀測；以 owner 真 `AsyncPostgresSaver.setup()` 後保存 migration rows。再對 app `GRANT USAGE, CREATE ON SCHEMA public` 及 `SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public`；app 不是 table owner，不給 superuser。這些觀測作 session evidence 傳給 PG-01，不用固定文字假裝 setup 已通過。

fixture `pg_case(tmp_path)` 依賴此 session fixture，建 `PgCase(app, owner, tmp_path/'unused.sqlite3', uuid4().hex)`。載入 policy 失敗不可 skip；只有完全沒有 live opt-in 時，PG 測試 module 在 import psycopg 前使用 `pytest.skip('isolated PostgreSQL live suite not enabled', allow_module_level=True)`。禁止 xdist 並行，避免故障權限互相影響。

- [x] **Step 4：增加前置成功節點 builder。** 在 cases.py 加入以下 builder，只新增 START→prerequisite→agents 邊，agent／publish 使用原 fixture 語意。

```python
def pg_builder(calls, agents=(4,)):
    from langgraph.graph import START, END, StateGraph
    from workflow_services import create_default_workflow_services
    from workflow_state import AgentGraphState
    services = create_default_workflow_services(rotator=object())
    builder = StateGraph(AgentGraphState)

    async def prerequisite(state):
        calls["prerequisite"] = calls.get("prerequisite", 0) + 1
        return {"execution_trace": [{"id": "pg-prerequisite"}]}

    builder.add_node("prerequisite", prerequisite)
    builder.add_edge(START, "prerequisite")
    names = []
    for agent in agents:
        name = f"agent_{agent}"
        names.append(name)
        async def run(state, agent=agent):
            result = await services.run_agent(agent, state)
            calls["nodes_returned"].append(agent)
            return result
        builder.add_node(name, run)
        builder.add_edge("prerequisite", name)

    async def publish(state):
        calls["published"] += 1
        return {"status": "done"}
    builder.add_node("publish", publish)
    builder.add_edge(names, "publish")
    builder.add_edge("publish", END)
    return builder
```

PG helper 中 builder 可顯式注入此版本；不改既有 SQLite assertions。

- [x] **Step 5：新增 PG-01 正向 smoke，先確認沒有偽通過。** `test_pg01_empty_setup_and_reopen_are_idempotent` 使用 session fixture 實際取得的 setup 前後 table 清單與 migration rows，前者為空、後者非空且 version 不重複；同一 endpoint 重開兩次後 migration rows 相同。app 再正常呼叫 `open_postgres_checkpointer()`，`SELECT current_database(), current_user` 必須符合 dedicated DB／非 owner app，`rolsuper=false`，各 saver tables owner≠app。**case 已加入；live 尚待 policy／image 準備。**

首次 smoke 只驗證 PG-01，不宣稱完整 PG suite 通過；entrypoint 若只收集到 PG-01，整體 result 必須標 `incomplete_suite`。測試 fixture 可以在單一 case 階段執行 debug，但正式交付的 mandatory ID 檢查不移除。

- [x] **Step 6：跑 SQLite 回歸與隔離 PG-01，提交 helper。** PG 真連線、migration、app setup 與未生成 SQLite checkpoint file 均由後續完整 live registry 覆蓋；helper 已以 `test: add real PostgreSQL workflow fixtures` 提交。

### Task 5：原稿、中間稿與跨 instance 恢復（PG-02／03／04／08）

**Files:** Modify `tests/test_workflow_postgres_live.py`、`tests/pg_validation/cases.py`。

- [x] **Step 1：寫 PG-02 完整 payload 與版本 roundtrip。** 同 thread、固定 state、同 agent 保存兩個不同正文；每次關閉 saver 後重開。版本保留原生型別，不轉 int。

```python
async def save_draft(case, state, text, *, thread="draft-job"):
    from workflow_quality_drafts import (checkpoint_draft_scope, quality_draft_node,
                                         checkpoint_unvalidated_draft)
    context = {"pipeline_id": "v1", "analyses": {}, "structured_outputs": {},
               "rag_context": {}, "context_digests": {}}
    async with open_postgres_checkpointer(case.app_endpoint.conninfo()) as saver:
        with checkpoint_draft_scope(saver, case.thread(thread)):
            async with quality_draft_node(4, state, context):
                context["structured_outputs"][4] = {"draft": text}
                context["market_context_manifests"] = {4: {"source": text}}
                context["rag_context"][4] = f"rag:{text}"
                context["context_digests"][4] = f"digest:{text}"
                await checkpoint_unvalidated_draft(4, text, context)

def test_pg02_original_and_intermediate_drafts_roundtrip(pg_case):
    state = initial_state()
    for text in ("original", "intermediate"):
        asyncio.run(save_draft(pg_case, state, text))
    rows = pg_case.drafts()
    assert len(rows) == 2
    versions = [row.checkpoint["channel_versions"]["quality_draft"] for row in rows]
    assert versions[1] > versions[0]
    fingerprints = set()
    for row, text in zip(rows, ("original", "intermediate"), strict=True):
        record = row.checkpoint["channel_values"]["quality_draft"]
        assert record["text"] == text and record["status"] == "unvalidated"
        assert record["structured_output"] == {"draft": text}
        assert record["market_context_manifest"] == {"source": text}
        assert record["rag_context"] == f"rag:{text}"
        assert record["context_digest"] == f"digest:{text}"
        fingerprints.add(record["input_fingerprint"])
    assert len(fingerprints) == 1
    assert not pg_case.sqlite_path.exists()
```

- [x] **Step 2：寫 PG-03／08 的 defer→新 saver→成功→再開。** 參數化 step-cache 關閉／TTL=0，套用現有 110000 字原稿、structured／RAG／digest 與 parse assertions。

```python
@pytest.mark.parametrize("cache_enabled,ttl", [(False, 3600), (True, 0), (False, 0)],
                         ids=["disabled", "expired", "disabled-expired"])
def test_pg03_deferred_draft_resumes_gate_once(pg_case, quality_runtime, monkeypatch, cache_enabled, ttl):
    calls, control, events = quality_runtime
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_ENABLED", cache_enabled)
    monkeypatch.setattr(step_cache, "AGENT_STEP_CACHE_SECONDS", ttl)
    control["raw_size"] = 110_000
    state = initial_state()
    with pytest.raises(AgentDeferredError):
        pg_case.execute(state, calls, builder=pg_builder(calls))
    saved = pg_case.drafts()[0].checkpoint["channel_values"]["quality_draft"]
    assert saved["text"] == "unvalidated-draft-4:" + "x" * 110_000
    assert not pg_case.snapshot(calls, builder=pg_builder(calls)).values.get("analyses")
    assert calls["published"] == 0
    control["deferred"] = False
    result = pg_case.execute(state, calls, builder=pg_builder(calls))
    assert result["analyses"]["4"] == "validated-result-4"
    assert calls["initial"] == [4] and calls["published"] == 1
    assert calls["prerequisite"] == 1
    assert [text for _, text in calls["validated"]].count(saved["text"]) == 2

def test_pg08_completed_graph_reopen_does_not_repeat_work_or_publish(pg_case, quality_runtime):
    calls, control, events = quality_runtime
    control["deferred"] = False
    state = initial_state()
    expected = pg_case.execute(state, calls, builder=pg_builder(calls))
    before = copy.deepcopy(calls)
    actual = pg_case.execute(state, calls, builder=pg_builder(calls))
    assert actual == expected and calls == before
```

以下兩案沿用原測試的 evidence 與中間修復稿斷言，並納入 mandatory registry；避免只手動保存中稿卻沒走過實際 repair。

```python
def test_pg02_intermediate_repair_survives_repeated_deferral(pg_case, intermediate_quality_runtime):
    calls, control, generated = intermediate_quality_runtime
    state = initial_state()
    for _ in range(2):
        with pytest.raises(AgentDeferredError):
            pg_case.execute(state, calls)
    assert generated == ["bad-json", "repaired-draft-1"]
    assert calls["rewrite"] == [(4, "repaired-draft-1"), (4, "repaired-draft-1")]
    rows = pg_case.drafts()
    assert len(rows) == 2
    assert rows[1].checkpoint["channel_versions"]["quality_draft"] > rows[0].checkpoint["channel_versions"]["quality_draft"]
    latest = rows[-1].checkpoint["channel_values"]["quality_draft"]
    assert latest["text"] == "repaired-draft-1"
    assert latest["structured_output"] == {"draft": "repaired-draft-1"}
    assert latest["rag_context"] == "retrieved-evidence-4"
    assert latest["context_digest"] == "digest-4"
    assert calls["published"] == 0
    control["deferred"] = False
    assert pg_case.execute(state, calls)["analyses"]["4"] == "validated-result-4"
    assert generated == ["bad-json", "repaired-draft-1"]

def test_pg03_restored_draft_does_not_refresh_evidence(pg_case, quality_runtime, monkeypatch):
    calls, control, events = quality_runtime
    state = initial_state()
    with pytest.raises(AgentDeferredError):
        pg_case.execute(state, calls)

    async def forbidden_refresh(*args, **kwargs):
        pytest.fail("resumed draft refreshed its evidence")

    generate = quality_gates.run_single_agent_async
    async def check_inputs(agent, data, context, rotator):
        assert context.get("_audit_retry_instruction")
        assert context["rag_context"][agent] == "retrieved-evidence-4"
        assert context["context_digests"][agent] == "digest-4"
        return await generate(agent, data, context, rotator)

    monkeypatch.setattr(quality_gates, "ensure_context_digest_async", forbidden_refresh)
    monkeypatch.setattr(quality_gates, "ensure_agent_rag_context_async", forbidden_refresh)
    monkeypatch.setattr(quality_gates, "run_single_agent_async", check_inputs)
    control["deferred"] = False
    assert pg_case.execute(state, calls)["status"] == "done"
    assert calls["initial"] == [4]
    assert any(event.get("phase") == "quality_draft_restored" for event in events)
```

- [x] **Step 3：寫 PG-04 草稿已保存後取消。** 只替換 fixture 模型在 audit retry 的取消事件，不改 saver／graph cancellation。

```python
def test_pg04_cancel_after_draft_resumes_without_partial_adoption(
        pg_case, quality_runtime, monkeypatch):
    calls, control, events = quality_runtime
    original_generate = quality_gates.run_single_agent_async

    async def cancel_retry(agent, data, context, rotator):
        if control["deferred"] and context.get("_audit_retry_instruction"):
            raise asyncio.CancelledError()
        return await original_generate(agent, data, context, rotator)

    monkeypatch.setattr(quality_gates, "run_single_agent_async", cancel_retry)
    state = initial_state()
    with pytest.raises(NodeCancelledError):
        pg_case.execute(state, calls, builder=pg_builder(calls))
    assert len(pg_case.drafts()) == 1
    snapshot = pg_case.snapshot(calls, builder=pg_builder(calls))
    assert snapshot.next == ("agent_4",)
    assert not snapshot.values.get("analyses") and not snapshot.values.get("agent_reports")
    assert calls["published"] == 0
    control["deferred"] = False
    assert pg_case.execute(state, calls, builder=pg_builder(calls))["status"] == "done"
    assert calls["initial"] == [4] and calls["prerequisite"] == 1
```

- [x] **Step 4：先觀察新 live cases 的正確失敗，再補直接相關 helper／adapter 缺陷到綠燈。** 完整 live registry 保留原稿、gate 重驗、完整 payload、version 與成功節點 assertions，並已通過。
- [x] **Step 5：SQLite＋新增 live subset 通過後提交。** 已以 `test: verify PostgreSQL draft and graph recovery` 提交。

### Task 6：thread／agent 隔離與真依賴失效（PG-05／06）

**Files:** Modify `tests/test_workflow_postgres_live.py`。

- [x] **Step 1：PG-05 用兩 thread 各自 `(4,14)`。** fixture 開 `deferred_agents={4}, wait_for_sibling=True`；為兩份 state 的 `ticker` 使用不同合成 token，生成正文附該 ticker，使錯拿另一 thread 的正文可被偵測。每個 thread 在 deferred 後確認 sibling 14 完成、4 pending；新 saver 恢復後只新增 4，14 不重跑。

```python
def test_pg05_threads_agents_and_completed_sibling_are_isolated(
        pg_case, quality_runtime, monkeypatch):
    calls, control, events = quality_runtime
    control.update(deferred_agents={4}, wait_for_sibling=True)
    generate = quality_gates.run_single_agent_async

    async def tagged(agent, data, context, rotator):
        return (await generate(agent, data, context, rotator)) + "|" + context["ticker"]

    monkeypatch.setattr(quality_gates, "run_single_agent_async", tagged)
    states = {}
    for name in ("first", "second"):
        state = initial_state()
        state["ticker"] = name
        state["normalized_financials"]["ticker"] = name
        states[name] = state
        with pytest.raises(AgentDeferredError):
            pg_case.execute(state, calls, thread=name, agents=(4, 14))
        assert pg_case.snapshot(calls, thread=name, agents=(4, 14)).next == ("agent_4",)
        for row in pg_case.drafts(name):
            assert row.config["configurable"]["thread_id"] == pg_case.thread(name)
            assert row.checkpoint["channel_values"]["quality_draft"]["text"].endswith("|" + name)
    control["deferred"] = False
    for name, state in states.items():
        result = pg_case.execute(state, calls, thread=name, agents=(4, 14))
        assert all(text.endswith("|" + name) for text in result["analyses"].values())
    assert calls["initial"].count(4) == 2 and calls["initial"].count(14) == 2
    assert calls["nodes_returned"].count(14) == 2
    assert calls["nodes_returned"].count(4) == 2 and calls["published"] == 2
```

- [x] **Step 2：PG-06a 固定 graph_state，僅真實更改 agent7 的上游 agent4 context。** 沿用 `tests/test_repair_dependencies.py::_context` 作輸入；三次值 old/new/old，生成器把上游值寫入正文、RAG／digest／manifest。assert 生成兩次、namespace 有兩個、第三次恢復第一份 evidence；不修改同 thread 的 `initial_state` 冒充失效。

```python
def test_pg06_draft_restoration_tracks_upstream_fingerprint(pg_case):
    from test_repair_dependencies import _context
    from workflow_quality_drafts import (checkpoint_draft_scope, quality_draft_node,
                                         initial_or_checkpointed_draft)
    generated = []
    fixed = {"analyses": {"4": "unchanged-graph"}}

    async def generate(agent, data, context, rotator):
        value = context["analyses"][4]
        generated.append(value)
        context.setdefault("rag_context", {})[7] = value
        context.setdefault("context_digests", {})[7] = value
        context.setdefault("market_context_manifests", {})[7] = {"value": value}
        return value

    async def run():
        for value in ("old", "new", "old"):
            context = _context()
            context["analyses"][4] = value
            async with open_postgres_checkpointer(pg_case.app_endpoint.conninfo()) as saver:
                with checkpoint_draft_scope(saver, pg_case.thread()):
                    async with quality_draft_node(7, fixed, context):
                        text = await initial_or_checkpointed_draft(7, {}, context, object(), generate)
                        assert text == value
                        assert context["rag_context"][7] == value
                        assert context["context_digests"][7] == value
                        assert context["market_context_manifests"][7] == {"value": value}
    asyncio.run(run())
    assert generated == ["old", "new"]
    assert len({row.config["configurable"]["checkpoint_ns"] for row in pg_case.drafts()}) == 2
```

- [x] **Step 3：PG-06b 保留真 RepairRound／replacement reducer。** 以現有 `tests/test_repair_dependencies.py::test_deferred_final_audit_resumes_only_uncommitted_round_in_real_graph` 為精確來源，保留 `complete`、`audit`、state、previous node、visits 與 prior 斷言；新增 PG 版本時，不匯入／使用 MemorySaver。將一次 compile 的 execute 區塊替換為下面真正關閉再重開 saver 的內容，其他模型／audit fixture 不變。

```python
config = {"configurable": {"thread_id": pg_case.thread("repair-deferred"), "checkpoint_ns": ""}}
async with open_postgres_checkpointer(pg_case.app_endpoint.conninfo()) as saver:
    graph = builder.compile(checkpointer=saver)
    with pytest.raises(AgentDeferredError):
        await graph.ainvoke(state, config)
    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("final_audit",)
    assert snapshot.values["analyses"][4] == "original 4"
    assert snapshot.values["analyses"][7] == "original 7"
allow_finish = True
async with open_postgres_checkpointer(pg_case.app_endpoint.conninfo()) as saver:
    graph = builder.compile(checkpointer=saver)
    result = await graph.ainvoke(None, config)
    assert result["analyses"]["4"] == "repaired 4"
    assert result["analyses"]["7"] == "repaired 7"
    assert result["invalidated_agents"] == []
```

新增名為 `test_pg06_dependency_repair_resumes_atomic_invalidated_round`；最終必須保留 `prior == ['already successful']` 與 `visits == [4,6,21,4,6,21,7]`。只替換生成與 audit fixture，不 monkeypatch 依賴圖、atomic transaction、provenance 或 reducer。

- [x] **Step 4：跑新 cases 與原 `test_repair_dependencies.py`，提交。** 正反例均觸及不同 namespace／upstream，並已以 `test: verify PostgreSQL isolation and dependency invalidation` 提交。

### Task 7：真草稿拒寫與舊 checkpoint 保留（PG-07）

**Files:** Modify `tests/pg_validation/cases.py`、`tests/test_workflow_postgres_live.py`。

- [x] **Step 1：寫精準 fault barrier。** 只在目標 thread／quality_draft namespace／指定正文時撤權；wrapper 必須呼叫真 `AsyncPostgresSaver.aput`，不能自己 raise 模擬 exception。將 `aput` 與 `aput_writes` 透過同 event-loop 的 `asyncio.Lock` 序列化這個案例，避免 graph 的非目標背景寫入撞到短暫撤權；這個 lock 只在故障測試 fixture，不修改 production。

```python
def deny_draft_write(monkeypatch, case, *, target_thread, matches):
    import psycopg
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from weakref import WeakKeyDictionary
    put = AsyncPostgresSaver.aput
    put_writes = AsyncPostgresSaver.aput_writes
    locks = WeakKeyDictionary()
    evidence = []

    def lock():
        loop = asyncio.get_running_loop()
        return locks.setdefault(loop, asyncio.Lock())

    async def guarded_put(self, config, checkpoint, metadata, new_versions):
        async with lock():
            cfg = config["configurable"]
            record = checkpoint["channel_values"].get("quality_draft", {})
            selected = (cfg["thread_id"] == target_thread
                        and cfg.get("checkpoint_ns", "").startswith("quality_draft/")
                        and matches(record))
            if not selected:
                return await put(self, config, checkpoint, metadata, new_versions)
            await case.permissions(False)
            try:
                return await put(self, config, checkpoint, metadata, new_versions)
            except psycopg.Error as exc:
                evidence.append({"namespace": cfg["checkpoint_ns"],
                                 "sqlstate": exc.sqlstate, "target_reached": True})
                raise
            finally:
                await case.permissions(True)

    async def guarded_writes(self, *args, **kwargs):
        async with lock():
            return await put_writes(self, *args, **kwargs)

    monkeypatch.setattr(AsyncPostgresSaver, "aput", guarded_put)
    monkeypatch.setattr(AsyncPostgresSaver, "aput_writes", guarded_writes)
    return evidence
```

在 `case.permissions(False)` 後，用 app 連線驗證 `has_table_privilege(current_user, 'checkpoints', 'INSERT')=false`，且 `SELECT` 權限仍在；角色不是 owner／superuser 的前置檢查不可省略。管理角色只能操作本次 schema。finally 恢復權限失敗時測試失敗，不吞掉。

- [x] **Step 2：寫原稿首次保存拒寫。** 先在**另一 thread** 用 `save_draft` 建可讀 baseline；不能在目標 namespace 預放原稿，否則生成器會恢復它而不嘗試寫新原稿。

```python
def test_pg07_original_draft_permission_denied_fails_closed(pg_case, quality_runtime, monkeypatch):
    import psycopg
    calls, control, events = quality_runtime
    state = initial_state()
    asyncio.run(save_draft(pg_case, state, "old-other-thread", thread="baseline"))
    before = [row.checkpoint for row in pg_case.drafts("baseline")]
    evidence = deny_draft_write(monkeypatch, pg_case,
        target_thread=pg_case.thread(),
        matches=lambda record: record.get("text", "").startswith("unvalidated-draft-4:"))
    with pytest.raises(psycopg.Error):
        pg_case.execute(state, calls, builder=pg_builder(calls))
    assert evidence and all(row["sqlstate"] == "42501" for row in evidence)
    assert not pg_case.drafts()
    assert [row.checkpoint for row in pg_case.drafts("baseline")] == before
    assert calls["initial"] == [4]
    assert not calls["parsed"] and not calls["validated"] and not calls["rewrite"]
    assert calls["published"] == 0 and calls["prerequisite"] == 1
    assert pg_case.snapshot(calls, builder=pg_builder(calls)).next == ("agent_4",)
```

- [x] **Step 3：寫中間修復稿拒寫，structured／identity 兩路徑均覆蓋。** `intermediate_quality_runtime` 會在中間稿保存前先做一次 validation，不能錯寫成 `validated == []`。

```python
def test_pg07_intermediate_draft_permission_denied_preserves_original(
        pg_case, intermediate_quality_runtime, monkeypatch):
    import psycopg
    calls, control, generated = intermediate_quality_runtime
    control["deferred"] = False
    barrier_counts = []

    def matches(record):
        selected = record.get("text") == "repaired-draft-1"
        if selected:
            barrier_counts.append((len(calls["validated"]), len(calls["parsed"])))
        return selected

    evidence = deny_draft_write(monkeypatch, pg_case,
        target_thread=pg_case.thread(), matches=matches)
    with pytest.raises(psycopg.Error):
        pg_case.execute(initial_state(), calls, builder=pg_builder(calls))
    assert len(evidence) == 1 and evidence[0]["sqlstate"] == "42501"
    assert generated == ["bad-json", "repaired-draft-1"]
    rows = pg_case.drafts()
    assert len(rows) == 1
    assert rows[0].checkpoint["channel_values"]["quality_draft"]["text"] == "bad-json"
    assert rows[0].checkpoint["channel_values"]["quality_draft"]["structured_output"] == {"draft": "bad-json"}
    assert barrier_counts == [(len(calls["validated"]), len(calls["parsed"]))]
    assert not calls["rewrite"] and calls["published"] == 0
    snapshot = pg_case.snapshot(calls, builder=pg_builder(calls))
    assert snapshot.next == ("agent_4",)
    assert not snapshot.values.get("analyses") and not snapshot.values.get("agent_reports")
```

- [x] **Step 4：跑權限故障與恢復後讀回，再跑原 SQLite failure cases。** PG-07 已觀察真 `42501` 與正確 namespace，恢復路徑及既有 SQLite failure cases 通過；已以 `test: prove PostgreSQL draft persistence fails closed` 提交。

### Task 8：native 負面檢查、完整結果與安全匯出

**Files:** Modify `tests/pg_validation/{cases,entrypoint,launcher}.py`、`tests/test_workflow_postgres_live.py`、offline policy/launcher tests。

- [x] **Step 1：增加只在隔離容器內執行的 native 反例。** 直接 `psycopg.pq.PGconn.connect` 對 `hostaddr=192.0.2.1 port=5432 dbname=invalid user=invalid connect_timeout=5`；預期 bad connection 且有界結束。這是保留給文件的 TEST-NET 位址，不指向正式 endpoint。一般 Python socket 仍應直接拒絕；wrapper 對其他 socket／hostaddr／service 的反例在 native 呼叫之前拒絕。

```python
def test_pg00_native_external_endpoint_is_unreachable():
    import time
    from psycopg import pq
    started = time.monotonic()
    conn = pq.PGconn.connect(
        b"hostaddr=192.0.2.1 port=5432 dbname=invalid user=invalid connect_timeout=5")
    try:
        assert conn.status == pq.ConnStatus.BAD
    finally:
        conn.finish()
    assert time.monotonic() - started < 10
```

不得在主機 runner 執行此 native 測試；PG module 沒有合法 live policy 時先 skip／拒絕，容器 inspect 未通過不 start。另用 monkeypatch fake native counter 測 wrapper 呼叫前拒絕，不依賴 native API 自帶網路拒絕能力。

- [x] **Step 2：加入 60 秒單案例 timeout 與 mandatory case registry。** 以 Linux 主執行緒 `signal.setitimer` fixture 包住整個 test，finally 清除 timer；所有 async 等待仍加有界 timeout，容器 watchdog 最多 10 分鐘。registry 固定如下，不從本次 collected set 自我生成；禁止 `-k`／skip 留下成功標記。

```python
EXPECTED_CASES = {
    "test_pg00_native_external_endpoint_is_unreachable",
    "test_pg01_empty_setup_and_reopen_are_idempotent",
    "test_pg02_original_and_intermediate_drafts_roundtrip",
    "test_pg02_intermediate_repair_survives_repeated_deferral[structured]",
    "test_pg02_intermediate_repair_survives_repeated_deferral[identity]",
    "test_pg03_deferred_draft_resumes_gate_once[disabled]",
    "test_pg03_deferred_draft_resumes_gate_once[expired]",
    "test_pg03_deferred_draft_resumes_gate_once[disabled-expired]",
    "test_pg03_restored_draft_does_not_refresh_evidence",
    "test_pg04_cancel_after_draft_resumes_without_partial_adoption",
    "test_pg05_threads_agents_and_completed_sibling_are_isolated",
    "test_pg06_draft_restoration_tracks_upstream_fingerprint",
    "test_pg06_dependency_repair_resumes_atomic_invalidated_round",
    "test_pg07_original_draft_permission_denied_fails_closed",
    "test_pg07_intermediate_draft_permission_denied_preserves_original[structured]",
    "test_pg07_intermediate_draft_permission_denied_preserves_original[identity]",
    "test_pg08_completed_graph_reopen_does_not_repeat_work_or_publish",
}
```

所有 node ID 再加固定檔名 `tests/test_workflow_postgres_live.py::` 比對。若新增必要 case，先更新明確 registry 與對應規格對照並重跑全部，不能讓未知 case 被靜默忽略。

- [x] **Step 3：新增 pytest plugin 的 structured-only result。** 收集 collection node IDs 與 setup/call/teardown outcome；test exception 只輸出 class name／SQLSTATE，不寫 traceback、conninfo、locals、provider key 或 raw PG log。session finish 驗證 collected exactly matches 本次批准 registry、每個 phase 完成、沒有 fail/skip/xfail／xpass、沒有 collection errors，再可標 `tests_passed`。實作結果判定純函式：

```python
def accepted_result(expected, collected, reports, *, exit_code):
    if (type(exit_code) is not int or exit_code != 0 or not expected
            or len(collected) != len(expected) or set(collected) != set(expected)):
        return False
    phases = {node: {} for node in collected}
    for report in reports:
        node, phase, outcome = report["nodeid"], report["when"], report["outcome"]
        if node not in phases or phase in phases[node] or report.get("wasxfail") is not None:
            return False
        phases[node][phase] = outcome
    return all(value == {"setup": "passed", "call": "passed", "teardown": "passed"}
               for value in phases.values())
```

插件僅 live 模式啟用，不改一般 suite 的 skip 語意。用 offline 單元測試涵蓋 zero collected、少一個參數案例、任一 skip／xfail、teardown failure、duplicate report、collection error 與缺 result；每種必須回失敗。mandatory registry 是固定 test names＋明確 parameter IDs，不從當次已收集到的 cases 自我生成。

- [x] **Step 4：entrypoint 寫 `/results/result.json`，主機匯出後再合併 cleanup。** JSON 限定欄位：schema、run ID、source manifest hash、base／derived image identity、實際版本、case IDs／phases／counts、network/socket/path assertions、exit code、server stop status。只有主機在精確 container cleanup 成功後才可產生 final `passed`；測試通過但 cleanup_failed 必須非零。

PGData、socket、SQLite 位於 tmpfs，容器停止即不可作持久 evidence；因此 `/results` 使用本次 container writable layer 而非 tmpfs，停止後 `docker cp` 只取 `result.json`。取回前驗證它是一般檔且有大小上限 1 MiB；主機解析 JSON 確認 run ID／image／manifest 一致、已知 schema／欄位，否則不當驗收證據。不匯出 PG log 或整個 `/tmp`／PGData。

- [x] **Step 5：完整 live run 與清理 failure injection 都通過後提交。** 已以 `test: require complete isolated PostgreSQL evidence` 提交；首次完整 live 結果只歸屬已記錄的 image／commit，未回填過往 fake 測試。

### Task 9：回歸、文件與交付

**Files:** Create `docs/postgres-isolated-verification.md`、`docs/postgres-isolated-verification-delivery-2026-09-06.md`；Modify `docs/system-architecture-map.md`、PG spec／本計畫的實際完成 checkbox。

- [x] **Step 1：全量 scoped offline 回歸。** 實際結果：`231 passed, 2 warnings in
  8.47s`；另跑 PG result/runtime/offline collection：`36 passed, 1 skipped in
  0.97s`。skip 是沒有 live policy，不能算 live pass。

```sh
"/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python" -B tests/run_prompt_boundary_tests.py \
  tests/test_postgres_validation_policy.py tests/test_postgres_validation_launcher.py \
  tests/test_workflow_checkpoint_resume.py tests/test_workflow_quality_draft_resume.py \
  tests/test_workflow_quality_draft_cold_imports.py tests/test_repair_dependencies.py \
  tests/test_runtime_paths.py tests/test_settings_env_loading.py \
  tests/test_storage_inventory.py tests/test_report_artifacts.py \
  -q -p no:cacheprovider --tb=short
```

預期 0 failure；計數讀實際輸出，不複製前輪數字。若改 runner guard，補一次全 suite collection 與按既有隔離 runner 的分組回歸，確保普通 tests 不被新 live policy 污染；全部 group 的覆蓋集合不得重複或遺漏。

- [x] **Step 2：從已 commit 的實作工作樹做完整 live run。** 啟動工具使用新建結果目錄；結果為 17/17 cases、51/51 phases、0 collection errors、exit code 0、PG stopped、container removed：

```sh
"/Volumes/X10 Pro Mac/stock-agent/.venv/bin/python" -B scripts/run_postgres_validation.py \
  --result-dir /tmp/stock-agent-pg-validation-final-20260906
```

若上述精確目錄已存在，CLI 必須拒絕覆寫，人工選新的 task-specific 名稱；不刪舊結果換取通過。驗收預期：mandatory PG cases 全部通過、0 skip、禁止連線反例成立、PG stopped、container removed、無 anonymous volume、正式設定未改。派生 image 留作 cache，列出精確 ID 與用途。

- [x] **Step 3：主 agent 親自逐項查證。** 已對照 PG-00～08 與隔離章核對完整 registry、class／SQLSTATE、cold reopen、原稿／中稿 payload、namespace／thread、取消／defer、真依賴失效、server stop 與 cleanup，不只採用 exit code。
- [x] **Step 4：寫操作文件。** 已新增 `docs/postgres-isolated-verification.md`，分開
  Docker build／offline validation，並記錄 fixed identity、non-root local-only trust、
  result schema、skip 與 cleanup_failed 語意。
- [x] **Step 5：寫交付紀錄。** 已新增本次實際 command／counts、commit／dirty、live
  image／runtime identity 與 cleanup 結果；明示未改 `.env`／正式
  `.venv`、未切換 production SQLite adapter、未 push／merge／restart／rebuild；OOS
  在這份 PG 交付完成後另依獨立計畫實作。
- [x] **Step 6：文件格式檢查與 scoped commit。** 文件與架構圖／spec／plan 狀態均已
  scoped 更新；提交前後執行 `git diff --check`，commit message：
  `docs: record isolated PostgreSQL verification evidence`。

## 規格覆蓋自我檢核（計畫層級，不是測試結果）

| 規格 | 對應 task |
| --- | --- |
| 目的、正式環境禁區與 OOS 分開 | 執行邊界、Task 9 |
| image／driver／版本固定 | 固定環境、Task 3 |
| native libpq、env／conninfo 拒絕 | Task 1、3、8 |
| 無外網／無 host mount／非 root／resource bounds | Task 2、3 |
| setup／完整草稿／版本／重開 | Task 4、5 |
| defer／cancel／已成功節點與 publish | Task 5 |
| 跨 thread／agent／平行 sibling | Task 6 |
| fingerprint 與真 RepairRound 失效 | Task 6 |
| 原稿／中稿真 42501，不在錯誤階段假通過 | Task 7 |
| skip／缺案例／timeout／cleanup fail-closed | Task 2、8 |
| SQLite 與 runtime/storage 相容性、文件與證據 | Task 4、9 |

本計畫不要求為補驗證而無條件改 production adapter；只有真失敗指出的直接缺陷才修正。計畫完成與測試／部署完成是不同狀態。
