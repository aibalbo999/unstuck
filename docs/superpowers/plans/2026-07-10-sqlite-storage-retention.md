# SQLite Storage Retention Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除同路徑 SQLite 重複維護，將備份間隔改為 30 天且每個 canonical DB 只留最新一份，並提供安全的終態 checkpoint 清理命令。

**Architecture:** `database_maintenance.py` 負責 canonical path 去重、30 天備份間隔與單一最新備份輪替；新的 `checkpoint_maintenance.py` 僅負責把 operational job state 映射到 LangGraph threads 並執行顯式清理。`maintenance.py` 提供 CLI wiring，Worker 只自動執行到期備份輪替，不自動刪除 checkpoint。

**Tech Stack:** Python 3.13、SQLite、pytest、既有 argparse maintenance CLI。

---

### Task 1: Canonical SQLite path 去重

**Files:**
- Modify: `backend/database_maintenance.py:14-28`
- Test: `tests/test_maintenance_commands.py`

- [ ] **Step 1: 寫入 failing test**

```python
def test_runtime_sqlite_paths_deduplicates_same_canonical_path(tmp_path):
    shared = tmp_path / "shared.sqlite3"
    task = tmp_path / "task.sqlite3"

    result = database_maintenance.runtime_sqlite_paths(
        cache_db_path=str(shared),
        task_db_path=str(task),
        checkpoint_backend="sqlite",
        checkpoint_path=str(tmp_path / "." / "shared.sqlite3"),
    )

    assert result == {"cache_db": str(shared), "task_db": str(task)}
```

- [ ] **Step 2: 驗證 RED**

Run: `$(scripts/project_python.sh) -m pytest tests/test_maintenance_commands.py::test_runtime_sqlite_paths_deduplicates_same_canonical_path -q`

Expected: FAIL，結果仍包含 `checkpoint_db`。

- [ ] **Step 3: 最小實作**

在 `runtime_sqlite_paths()` 內依 `cache_db`、`task_db`、`checkpoint_db` 優先序呼叫 helper：

```python
def _add_unique_database(paths: dict[str, str], label: str, value: str) -> None:
    identity = Path(value).expanduser().resolve(strict=False)
    existing = {Path(path).expanduser().resolve(strict=False) for path in paths.values()}
    if identity not in existing:
        paths[label] = value
```

- [ ] **Step 4: 驗證 GREEN 與既有 maintenance tests**

Run: `$(scripts/project_python.sh) -m pytest tests/test_maintenance_commands.py -q`

Expected: PASS。

### Task 2: 30 天備份間隔與單一最新備份

**Files:**
- Modify: `backend/settings/storage.py:66-76`
- Modify: `backend/database_maintenance.py:31-72`
- Modify: `README.md`
- Modify: `docs/operator-guide.md`
- Test: `tests/test_settings_env_loading.py`
- Test: `tests/test_maintenance_commands.py`

- [ ] **Step 1: 寫入設定、間隔與單一保留 failing tests**

```python
def test_sqlite_backup_pruning_dry_run_preserves_files(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = backup_dir / "cache_db-20260625.sqlite3"
    recent = backup_dir / "cache_db-20260628.sqlite3"
    unknown = backup_dir / "manual-archive.sqlite3"
    for path in (old, recent, unknown):
        path.write_bytes(b"backup")

    result = database_maintenance.maintain_sqlite_databases(
        {}, backup_dir=str(backup_dir), retention_days=3, write=False,
        now=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )

    assert result["backup_pruning"]["candidates"] == [str(old)]
    assert old.exists() and recent.exists() and unknown.exists()
```

並在既有 `test_blank_storage_path_env_vars_fall_back_to_defaults()` 的 `keys` 加入 `SQLITE_BACKUP_RETENTION_DAYS` 與 `SQLITE_BACKUP_INTERVAL_DAYS`，斷言 default 分別為 `1` 與 `30`。

另新增 write test：最近已有 `task_db-20260701.sqlite3`，以 `now=2026-07-10`、`backup_interval_days=30` 執行時，結果為 `skipped_interval`，且 `wal_checkpoint.status` 與 `vacuum.status` 都是 `skipped_backup_interval`；以 `now=2026-07-31` 執行時才建立備份並執行一次維護。

- [ ] **Step 2: 驗證 RED**

Run: `$(scripts/project_python.sh) -m pytest tests/test_settings_env_loading.py tests/test_maintenance_commands.py -q`

Expected: FAIL，缺少 retention setting/argument/result。

- [ ] **Step 3: 實作設定與純規則 helper**

```python
SQLITE_BACKUP_RETENTION_DAYS = env_int("SQLITE_BACKUP_RETENTION_DAYS", 3)
```

新增 `SQLITE_BACKUP_INTERVAL_DAYS = env_int("SQLITE_BACKUP_INTERVAL_DAYS", 30)` 與 `SQLITE_BACKUP_RETENTION_DAYS = env_int("SQLITE_BACKUP_RETENTION_DAYS", 1)`。`_backup_plan()` 找同 label 最新 regular backup；未達 interval 回報 `skipped_interval`，達期才 `pending`。`_prune_backup_files()` 只接受 `^(cache_db|task_db|checkpoint_db)-(\d{8})\.sqlite3$`，cutoff 為 UTC 當日（retention=1），但每個目前 runtime DB label 仍保留最新一份；更舊同 label 與已不屬於目前 runtime DB labels 的 managed backup 可列為 candidates，write 才 `unlink()`。非正數 interval/retention 一律 fail closed。

- [ ] **Step 4: 寫入 write-mode failing test**

```python
def test_sqlite_backup_pruning_write_deletes_only_managed_expired_files(tmp_path):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    old = backup_dir / "cache_db-20260625.sqlite3"
    recent = backup_dir / "cache_db-20260628.sqlite3"
    unknown = backup_dir / "manual-archive.sqlite3"
    for path in (old, recent, unknown):
        path.write_bytes(b"backup")

    result = database_maintenance.maintain_sqlite_databases(
        {}, backup_dir=str(backup_dir), retention_days=3, write=True,
        now=datetime(2026, 6, 29, tzinfo=timezone.utc),
    )

    assert result["backup_pruning"]["deleted"] == [str(old)]
    assert not old.exists()
    assert recent.exists() and unknown.exists()
```

- [ ] **Step 5: 驗證 RED、完成最小 write 實作、再驗證 GREEN**

Run: `$(scripts/project_python.sh) -m pytest tests/test_settings_env_loading.py tests/test_maintenance_commands.py -q`

Expected: PASS。

- [ ] **Step 6: 更新操作文件**

記錄 `SQLITE_BACKUP_INTERVAL_DAYS=30`、`SQLITE_BACKUP_RETENTION_DAYS=1`、UTC cutoff、每個目前 runtime DB label 保留最新一份、已不屬於目前 labels 的 managed backup 會被清理、未到期時跳過 WAL/VACUUM、unknown archive 不受管理，以及 dry-run/write 行為。

### Task 3: 終態 checkpoint 顯式清理

**Files:**
- Create: `backend/checkpoint_maintenance.py`
- Modify: `backend/maintenance.py`
- Modify: `README.md`
- Modify: `docs/operator-guide.md`
- Test: `tests/test_checkpoint_maintenance.py`
- Test: `tests/test_maintenance_commands.py`

- [ ] **Step 1: 寫入 checkpoint selection failing test**

```python
def _seed_checkpoint_databases(tmp_path):
    task_db = tmp_path / "task.sqlite3"
    checkpoint_db = tmp_path / "checkpoint.sqlite3"
    with sqlite3.connect(task_db) as conn:
        conn.execute("CREATE TABLE analysis_jobs (job_id TEXT PRIMARY KEY, status TEXT NOT NULL)")
        conn.executemany(
            "INSERT INTO analysis_jobs (job_id, status) VALUES (?, ?)",
            [("done-job", "done"), ("running-job", "running")],
        )
    with sqlite3.connect(checkpoint_db) as conn:
        conn.execute("CREATE TABLE checkpoints (thread_id TEXT, checkpoint BLOB, metadata BLOB)")
        conn.execute("CREATE TABLE writes (thread_id TEXT, value BLOB)")
        for thread_id in ("done-job:v1", "running-job:v1", "unknown:v1"):
            conn.execute(
                "INSERT INTO checkpoints (thread_id, checkpoint, metadata) VALUES (?, ?, ?)",
                (thread_id, b"checkpoint", b"metadata"),
            )
            conn.execute("INSERT INTO writes (thread_id, value) VALUES (?, ?)", (thread_id, b"write"))
    return task_db, checkpoint_db


def _threads(checkpoint_db):
    with sqlite3.connect(checkpoint_db) as conn:
        return {row[0] for row in conn.execute("SELECT DISTINCT thread_id FROM checkpoints")}


def test_cleanup_terminal_checkpoints_dry_run_selects_only_terminal_jobs(tmp_path):
    task_db, checkpoint_db = _seed_checkpoint_databases(tmp_path)
    result = cleanup_terminal_checkpoints(
        checkpoint_db_path=str(checkpoint_db), task_db_path=str(task_db), write=False,
    )
    assert result["candidate_threads"] == 1
    assert result["deleted_threads"] == 0
    assert _threads(checkpoint_db) == {"done-job:v1", "running-job:v1", "unknown:v1"}
```

- [ ] **Step 2: 驗證 RED**

Run: `$(scripts/project_python.sh) -m pytest tests/test_checkpoint_maintenance.py -q`

Expected: FAIL，module 尚不存在。

- [ ] **Step 3: 實作 dry-run summary**

`cleanup_terminal_checkpoints()` 應回傳：

```python
{
    "checkpoint_db_exists": True,
    "task_db_exists": True,
    "schema_ready": True,
    "candidate_threads": 1,
    "checkpoint_rows": 1,
    "write_rows": 1,
    "checkpoint_bytes": 18,
    "write_bytes": 5,
    "deleted_threads": 0,
    "dry_run": True,
}
```

- [ ] **Step 4: 寫入 write 與缺失 schema failing tests**

```python
def test_cleanup_terminal_checkpoints_write_preserves_active_and_unmatched_threads(tmp_path):
    task_db, checkpoint_db = _seed_checkpoint_databases(tmp_path)
    result = cleanup_terminal_checkpoints(
        checkpoint_db_path=str(checkpoint_db), task_db_path=str(task_db), write=True,
    )
    assert result["deleted_threads"] == 1
    assert _threads(checkpoint_db) == {"running-job:v1", "unknown:v1"}


def test_cleanup_terminal_checkpoints_missing_schema_is_safe(tmp_path):
    task_db = tmp_path / "task.sqlite3"
    checkpoint_db = tmp_path / "checkpoint.sqlite3"
    sqlite3.connect(task_db).close()
    sqlite3.connect(checkpoint_db).close()
    result = cleanup_terminal_checkpoints(
        checkpoint_db_path=str(checkpoint_db), task_db_path=str(task_db), write=True,
    )
    assert result["schema_ready"] is False
    assert result["deleted_threads"] == 0
```

- [ ] **Step 5: 驗證 RED、實作批次刪除、再驗證 GREEN**

以每批最多 200 threads 執行 `DELETE FROM writes`，再執行 `DELETE FROM checkpoints`；transaction 成功後才 commit。

Run: `$(scripts/project_python.sh) -m pytest tests/test_checkpoint_maintenance.py -q`

Expected: PASS。

- [ ] **Step 6: 加入 CLI 與 contract test**

新增：

```text
cleanup-terminal-checkpoints [--checkpoint-db-path PATH] [--task-db-path PATH] [--write]
```

Run: `$(scripts/project_python.sh) -m pytest tests/test_maintenance_commands.py tests/test_checkpoint_maintenance.py -q`

Expected: PASS。

### Task 4: 離線清理、部署與驗證

**Files:**
- Runtime data only: `backend/cache/**`

- [ ] **Step 1: 執行完整回歸測試**

Run:

```bash
$(scripts/project_python.sh) -m pytest \
  tests/test_checkpoint_maintenance.py \
  tests/test_maintenance_commands.py \
  tests/test_runtime_paths.py \
  tests/test_settings_env_loading.py \
  tests/test_storage_inventory.py \
  tests/test_report_artifacts.py -q
```

Expected: PASS。

- [ ] **Step 2: 正常停止 runtime 並確認無 process 開啟 canonical DB**

Run: `tmux send-keys -t stock-agent C-c`，再確認 `pgrep` 與 `lsof` 無結果。

- [ ] **Step 3: dry-run 與 write 清理終態 checkpoint**

Run:

```bash
scripts/maintenance.sh cleanup-terminal-checkpoints
scripts/maintenance.sh cleanup-terminal-checkpoints --write
```

Expected: dry-run/write candidate counts 相同，active/unmatched 為 0 deletions。

- [ ] **Step 4: 單次 SQLite 維護並移除舊重複備份**

保留當日每個 canonical DB 最新 backup；移除所有舊 managed backup 與重複的 `checkpoint_db-20260710.sqlite3`，不刪 unknown archive。只有當 interval 到期時才各對 canonical DB 執行一次 checkpoint/`VACUUM`。

- [ ] **Step 5: 正式重啟與驗證**

Run:

```bash
tmux new-session -d -s stock-agent 'cd /Users/balbomacmini/Desktop/onstock/stock-agent && ./start_mac.command'
lsof -nP -iTCP:8080 -sTCP:LISTEN
pgrep -fl 'start_mac.command|worker_main.py --role all|uvicorn api:app'
$(scripts/project_python.sh) scripts/doctor_runtime.py --json
curl -fsS http://127.0.0.1:8080/
curl -fsS 'http://127.0.0.1:8080/api/reports?page=1&limit=1'
curl -fsS http://127.0.0.1:8080/api/watchlist
curl -fsS http://127.0.0.1:8080/api/decision-tracking
```

Expected: 8080 與 Worker 存活、doctor paths 正確、四個 HTTP endpoints 回應成功。
