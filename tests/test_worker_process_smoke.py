import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_worker_main_cli_exposes_burst_options_for_smoke_tests():
    result = subprocess.run(
        [sys.executable, str(ROOT / "backend" / "worker_main.py"), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--burst" in result.stdout
    assert "--max-jobs" in result.stdout


def test_operator_docs_describe_split_worker_startup():
    combined_docs = "\n".join(
        [
            (ROOT / "README.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "operator-guide.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8"),
        ]
    )

    for expected in [
        "redis-server",
        "python backend/worker_main.py --role all",
        "uvicorn api:app --app-dir backend",
        "TASK_QUEUE_BACKEND=local",
        "RQ_JOB_MAX_RETRIES",
        "SIGTERM",
    ]:
        assert expected in combined_docs
    assert "API task queue requires Redis and RQ" in combined_docs
    assert "queue / schedulers / maintenance" in combined_docs


@pytest.mark.integration
def test_rq_worker_process_smoke_finishes_one_job_without_api_consuming_it():
    redis_url = os.getenv("REDIS_TEST_URL")
    if not redis_url:
        pytest.skip("Set REDIS_TEST_URL to run the Redis/RQ worker smoke test.")

    from redis import Redis
    from rq import Queue

    queue_name = f"stock-analysis-smoke-{uuid.uuid4().hex}"
    job_id = f"smoke-{uuid.uuid4().hex}"
    connection = Redis.from_url(redis_url)
    queue = Queue(queue_name, connection=connection)
    queue.empty()
    job = queue.enqueue_call(func="math.sqrt", args=(81,), job_id=job_id, result_ttl=60, failure_ttl=60)
    env = {
        **os.environ,
        "REDIS_URL": redis_url,
        "TASK_QUEUE_BACKEND": "rq",
        "TASK_QUEUE_NAME": queue_name,
        "REPORT_STORAGE_BACKEND": "memory",
        "CACHE_BACKEND": "memory",
    }

    api_probe = subprocess.run(
        [sys.executable, "-c", f"import sys; sys.path.insert(0, {str(ROOT / 'backend')!r}); import api"],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    assert api_probe.returncode == 0, api_probe.stderr
    job.refresh()
    assert job.get_status(refresh=True) == "queued"

    worker = subprocess.run(
        [
            sys.executable,
            str(ROOT / "backend" / "worker_main.py"),
            "--role",
            "queue",
            "--burst",
            "--max-jobs",
            "1",
        ],
        cwd=str(ROOT),
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )

    job.refresh()
    try:
        assert worker.returncode == 0, worker.stderr
        assert job.is_finished
        assert job.result == 9.0
    finally:
        queue.empty()
        connection.delete(job.key)
        connection.close()
