from datetime import datetime, timedelta, timezone

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from queue_maintenance import cleanup_stale_failed_jobs  # noqa: E402


class FakeJob:
    def __init__(self, job_id: str, *, ended_at=None, created_at=None):
        self.id = job_id
        self.ended_at = ended_at
        self.created_at = created_at


class FakeRegistry:
    def __init__(self, jobs):
        self.jobs = {job.id: job for job in jobs}
        self.removed = []

    def get_job_ids(self):
        return list(self.jobs)

    def remove(self, job, *, delete_job=False):
        self.removed.append((job.id, delete_job))
        self.jobs.pop(job.id, None)


class FakeQueue:
    name = "stock-analysis"

    def __init__(self, jobs):
        self.failed_job_registry = FakeRegistry(jobs)

    def fetch_job(self, job_id):
        return self.failed_job_registry.jobs.get(job_id)


class FakeTaskQueue:
    def __init__(self, queue):
        self.queues = {queue.name: queue}
        self.queue = queue


def test_cleanup_stale_failed_jobs_dry_run_reports_candidates_without_removing():
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)
    queue = FakeQueue([
        FakeJob("old-1", ended_at=now - timedelta(days=8)),
        FakeJob("old-2", ended_at=now - timedelta(days=9)),
        FakeJob("recent", ended_at=now - timedelta(hours=2)),
    ])

    result = cleanup_stale_failed_jobs(FakeTaskQueue(queue), now=now.timestamp(), write=False)

    assert result["dry_run"] is True
    assert result["failed_jobs_scanned"] == 3
    assert result["stale_failed_jobs"] == 2
    assert result["deleted_jobs"] == 0
    assert queue.failed_job_registry.removed == []


def test_cleanup_stale_failed_jobs_write_removes_only_stale_jobs_and_deletes_data():
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)
    queue = FakeQueue([
        FakeJob("old", ended_at=now - timedelta(days=8)),
        FakeJob("recent", ended_at=now - timedelta(hours=2)),
    ])

    result = cleanup_stale_failed_jobs(FakeTaskQueue(queue), now=now.timestamp(), write=True)

    assert result["dry_run"] is False
    assert result["deleted_jobs"] == 1
    assert queue.failed_job_registry.removed == [("old", True)]
    assert set(queue.failed_job_registry.jobs) == {"recent"}


def test_cleanup_stale_failed_jobs_does_not_delete_jobs_without_age_evidence():
    now = datetime(2026, 8, 16, tzinfo=timezone.utc)
    queue = FakeQueue([FakeJob("unknown")])

    result = cleanup_stale_failed_jobs(FakeTaskQueue(queue), now=now.timestamp(), write=True)

    assert result["failed_jobs_scanned"] == 1
    assert result["unclassified_jobs"] == 1
    assert result["stale_failed_jobs"] == 0
    assert result["deleted_jobs"] == 0
    assert queue.failed_job_registry.removed == []
