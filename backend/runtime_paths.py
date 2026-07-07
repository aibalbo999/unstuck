"""Canonical runtime path map for operators, code, and agent navigation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RuntimePaths:
    output_dir: Path
    cache_dir: Path
    report_index_db: Path
    operational_db: Path
    task_db: Path
    langgraph_checkpoint_path: Path
    legacy_decision_tracking_db: Path
    report_storage_backend: str = "local"
    cache_backend: str = "redis"
    redis_url: str = "redis://localhost:6379/0"
    task_queue_backend: str = "rq"
    task_queue_name: str = "stock-analysis"

    @classmethod
    def from_values(
        cls,
        *,
        output_dir: str | Path,
        cache_dir: str | Path,
        report_index_db: str | Path | None = None,
        operational_db: str | Path | None = None,
        task_db: str | Path | None = None,
        langgraph_checkpoint_path: str | Path | None = None,
        report_storage_backend: str = "local",
        cache_backend: str = "redis",
        redis_url: str = "redis://localhost:6379/0",
        task_queue_backend: str = "rq",
        task_queue_name: str = "stock-analysis",
    ) -> "RuntimePaths":
        cache_path = Path(cache_dir)
        operational_path = Path(operational_db) if operational_db is not None else cache_path / "operational.sqlite3"
        return cls(
            output_dir=Path(output_dir),
            cache_dir=cache_path,
            report_index_db=Path(report_index_db) if report_index_db is not None else cache_path / "stock_agent_cache.sqlite3",
            operational_db=operational_path,
            task_db=Path(task_db) if task_db is not None else operational_path,
            langgraph_checkpoint_path=(
                Path(langgraph_checkpoint_path)
                if langgraph_checkpoint_path is not None
                else cache_path / "stock_agent_cache.sqlite3"
            ),
            legacy_decision_tracking_db=cache_path / "decision_tracking.sqlite3",
            report_storage_backend=str(report_storage_backend),
            cache_backend=str(cache_backend),
            redis_url=str(redis_url),
            task_queue_backend=str(task_queue_backend),
            task_queue_name=str(task_queue_name),
        )

    def as_dict(self) -> dict[str, dict[str, object] | str]:
        return {
            "output_dir": str(self.output_dir),
            "cache_dir": str(self.cache_dir),
            "report_index_db": {
                "path": str(self.report_index_db),
                "canonical": True,
                "owner": "report_index",
            },
            "operational_db": {
                "path": str(self.operational_db),
                "canonical": True,
                "owner": "operational stores",
            },
            "task_db": {
                "path": str(self.task_db),
                "canonical": True,
                "owner": "job_store",
            },
            "decision_tracking_db": {
                "path": str(self.task_db),
                "canonical": True,
                "owner": "decision_tracking_store",
            },
            "legacy_decision_tracking_db": {
                "path": str(self.legacy_decision_tracking_db),
                "canonical": False,
                "owner": "legacy migration only",
            },
            "langgraph_checkpoint_path": {
                "path": str(self.langgraph_checkpoint_path),
                "canonical": True,
                "owner": "workflow checkpointing",
            },
            "report_storage_backend": self.report_storage_backend,
            "cache_backend": self.cache_backend,
            "redis_url": self.redis_url,
            "task_queue_backend": self.task_queue_backend,
            "task_queue_name": self.task_queue_name,
        }


def current_runtime_paths() -> RuntimePaths:
    from settings import runtime_limits, storage

    return RuntimePaths.from_values(
        output_dir=storage.OUTPUT_DIR,
        cache_dir=storage.CACHE_DIR,
        report_index_db=storage.CACHE_DB_PATH,
        operational_db=storage.OPERATIONAL_DB_PATH,
        task_db=storage.TASK_DB_PATH,
        langgraph_checkpoint_path=storage.LANGGRAPH_CHECKPOINT_PATH,
        report_storage_backend=storage.REPORT_STORAGE_BACKEND,
        cache_backend=storage.CACHE_BACKEND,
        redis_url=runtime_limits.REDIS_URL,
        task_queue_backend=runtime_limits.TASK_QUEUE_BACKEND,
        task_queue_name=runtime_limits.TASK_QUEUE_NAME,
    )


def runtime_path_summary() -> dict[str, dict[str, object] | str]:
    return current_runtime_paths().as_dict()


__all__ = ["RuntimePaths", "current_runtime_paths", "runtime_path_summary"]
