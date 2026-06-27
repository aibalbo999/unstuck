import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api_routes.reports import ReportRouteDeps, create_reports_router
from data_trust import data_snapshot_filename_for_report
from report_history_service import delete_report_files, download_report_file, get_report_file, list_reports
from reporting import ReportBundle
from storage.report_storage import InMemoryStorage, StoredReport, StoredReportContent


class RecordingStorage:
    def __init__(self, *, fail_on_key: str | None = None):
        self.fail_on_key = fail_on_key
        self.saved: dict[str, StoredReportContent] = {}
        self.order: list[str] = []
        self.deleted: list[str] = []

    def save_report(self, key: str, content: bytes, *, content_type: str) -> StoredReport:
        label = _label_for_key(key)
        self.order.append(f"save:{label}")
        if key == self.fail_on_key:
            raise RuntimeError(f"boom: {key}")
        metadata = StoredReport(
            key=key,
            size=len(content),
            content_type=content_type,
            updated_at=datetime.now(timezone.utc),
        )
        self.saved[key] = StoredReportContent(metadata=metadata, content=bytes(content))
        return metadata

    def get_report(self, key: str) -> StoredReportContent | None:
        return self.saved.get(key)

    def delete_report(self, key: str) -> bool:
        self.deleted.append(key)
        return self.saved.pop(key, None) is not None

    def exists(self, key: str) -> bool:
        return key in self.saved

    def list_reports(self, *, prefix: str = "") -> list[StoredReport]:
        return [
            item.metadata
            for key, item in sorted(self.saved.items())
            if key.startswith(prefix)
        ]


class RecordingRepository:
    def __init__(self, order: list[str] | None = None, *, metadata_exists: bool = False):
        self.order = order if order is not None else []
        self.metadata_exists = metadata_exists
        self.upserts: list[dict] = []
        self.deleted: list[tuple[str, str | None]] = []

    def upsert(self, filename: str, **kwargs):
        self.order.append("index")
        self.upserts.append({"filename": filename, **kwargs})
        return {"filename": filename, "indexed": True}

    def delete(self, filename: str, output_dir: str | None = None) -> None:
        self.deleted.append((filename, output_dir))

    def exists(self, filename: str, output_dir: str | None = None) -> bool:
        return self.metadata_exists


class FailingUpsertRepository(RecordingRepository):
    def upsert(self, filename: str, **kwargs):
        self.order.append("index")
        raise RuntimeError("metadata upsert failed")


class FailingDeleteRepository(RecordingRepository):
    def delete(self, filename: str, output_dir: str | None = None) -> None:
        self.deleted.append((filename, output_dir))
        raise RuntimeError("metadata delete failed")


class RecordingLock:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _label_for_key(key: str) -> str:
    if key.endswith(".html"):
        return "html"
    if key.endswith(".md"):
        return "md"
    if key.endswith(".data.json"):
        return "data"
    return key


def test_persist_report_bundle_saves_content_before_indexing():
    from report_persistence import persist_report_bundle

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = RecordingStorage()
    repository = RecordingRepository(storage.order)

    result = persist_report_bundle(
        filename=filename,
        html_content="<html>台達電</html>",
        markdown_content="# 台達電\n",
        data_snapshot={"ticker": "2308.TW", "data_trust": {"status": "fresh"}},
        storage=storage,
        output_dir="/reports",
        repository=repository,
    )

    assert storage.order == ["save:html", "save:md", "save:data", "index"]
    assert result["filename"] == filename
    assert result["md_filename"] == "2308_TW_v2_report_20260626_120000.md"
    assert result["data_filename"] == data_snapshot_filename_for_report(filename)
    assert result["html_key"] == f"2026-06/2308.TW/{filename}"
    assert result["md_key"] == f"2026-06/2308.TW/{result['md_filename']}"
    assert result["data_key"] == f"2026-06/2308.TW/{result['data_filename']}"
    assert repository.upserts == [
        {
            "filename": filename,
            "output_dir": "/reports",
            "html_content": "<html>台達電</html>",
            "markdown_content": "# 台達電\n",
            "data_trust": {"status": "fresh"},
        }
    ]
    assert storage.saved[result["data_key"]].content == json.dumps(
        {"ticker": "2308.TW", "data_trust": {"status": "fresh"}},
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")


def test_persist_report_bundle_rolls_back_saved_content_when_data_save_fails():
    from report_persistence import persist_report_bundle

    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    data_filename = f"2026-06/2308.TW/{data_snapshot_filename_for_report(filename)}"
    storage = RecordingStorage(fail_on_key=data_filename)
    repository = RecordingRepository(storage.order)

    try:
        persist_report_bundle(
            filename=filename,
            html_content="<html></html>",
            markdown_content="# report\n",
            data_snapshot={"ticker": "2308.TW"},
            storage=storage,
            output_dir="/reports",
            repository=repository,
        )
    except RuntimeError as exc:
        assert str(exc) == f"boom: {data_filename}"
    else:
        raise AssertionError("expected data save failure")

    assert storage.deleted == [f"2026-06/2308.TW/{md_filename}", f"2026-06/2308.TW/{filename}"]
    assert filename not in storage.saved
    assert md_filename not in storage.saved
    assert repository.upserts == []
    assert "index" not in storage.order


def test_persist_report_bundle_rolls_back_saved_content_when_metadata_upsert_fails():
    from report_persistence import persist_report_bundle

    filename = "2308_TW_v2_report_20260626_120000.html"
    storage = RecordingStorage()
    repository = FailingUpsertRepository(storage.order)

    try:
        persist_report_bundle(
            filename=filename,
            html_content="<html></html>",
            markdown_content="# report\n",
            data_snapshot={"ticker": "2308.TW"},
            storage=storage,
            output_dir="/reports",
            repository=repository,
        )
    except RuntimeError as exc:
        assert str(exc) == "metadata upsert failed"
    else:
        raise AssertionError("expected metadata upsert failure")

    assert storage.deleted == [
        f"2026-06/2308.TW/{data_snapshot_filename_for_report(filename)}",
        "2026-06/2308.TW/2308_TW_v2_report_20260626_120000.md",
        f"2026-06/2308.TW/{filename}",
    ]
    assert storage.saved == {}


def test_report_bundle_keys_partition_by_report_month_and_ticker():
    from report_persistence import report_bundle_keys_for_filename

    filename = "2308_TW_v2_report_20260626_120000.html"

    keys = report_bundle_keys_for_filename(filename)

    assert keys.filename == filename
    assert keys.html_key == f"2026-06/2308.TW/{filename}"
    assert keys.md_key == "2026-06/2308.TW/2308_TW_v2_report_20260626_120000.md"
    assert keys.data_key == f"2026-06/2308.TW/{data_snapshot_filename_for_report(filename)}"


def test_list_reports_uses_metadata_without_syncing_nonlocal_storage(tmp_path):
    from report_persistence import persist_report_bundle

    storage = InMemoryStorage()
    missing_output_dir = tmp_path / "missing-output-dir"
    filename = "2308_TW_v2_report_20260626_120000.html"
    persist_report_bundle(
        filename=filename,
        html_content="<html><body>台達電</body></html>",
        markdown_content="# 投資建議\n\n買入\n",
        data_snapshot={"ticker": "2308.TW", "data_trust": {"status": "fresh"}},
        storage=storage,
        output_dir=str(missing_output_dir),
    )

    result = list_reports(
        page=1,
        limit=10,
        q="",
        pipeline="all",
        recommendation="all",
        data_trust="all",
        output_dir=str(missing_output_dir),
        report_cache={},
        storage=storage,
    )

    assert [report["filename"] for report in result["reports"]] == [filename]


def test_get_report_file_reads_storage_and_repairs_html():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(
        filename,
        '<p>台達電（<a href="http://2308.TW">2308.TW</a>）</p>'.encode("utf-8"),
        content_type="text/html",
    )

    response = get_report_file(filename, "/missing-output-dir", storage=storage)

    assert response.status_code == 200
    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in response.body.decode("utf-8")


def test_download_report_file_reads_storage_for_html_markdown_and_data():
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    data_filename = data_snapshot_filename_for_report(filename)
    storage.save_report(
        filename,
        '<a href="http://2308.TW">2308.TW</a>'.encode("utf-8"),
        content_type="text/html",
    )
    storage.save_report(md_filename, "# 台達電\n".encode("utf-8"), content_type="text/markdown")
    storage.save_report(data_filename, b'{"ticker":"2308.TW"}', content_type="application/json")

    html_response = download_report_file(filename, "/missing-output-dir", "html", storage=storage)
    md_response = download_report_file(filename, "/missing-output-dir", "md", storage=storage)
    data_response = download_report_file(filename, "/missing-output-dir", "data", storage=storage)

    assert html_response.status_code == 200
    assert html_response.headers["content-disposition"] == f"attachment; filename={filename}"
    assert 'href="https://tw.stock.yahoo.com/quote/2308.TW"' in html_response.body.decode("utf-8")
    assert md_response.status_code == 200
    assert md_response.body == "# 台達電\n".encode("utf-8")
    assert md_response.headers["content-disposition"] == f"attachment; filename={md_filename}"
    assert md_response.headers["content-type"].startswith("text/markdown")
    assert data_response.status_code == 200
    assert data_response.body == b'{"ticker":"2308.TW"}'
    assert data_response.headers["content-disposition"] == f"attachment; filename={data_filename}"
    assert data_response.headers["content-type"].startswith("application/json")


def test_refresh_data_snapshot_reads_and_updates_partitioned_storage(tmp_path, monkeypatch):
    import report_refresh_service
    from report_persistence import report_bundle_keys_for_filename

    monkeypatch.setattr(report_refresh_service, "upsert_report_metadata", lambda *args, **kwargs: {"filename": args[0]})
    storage = InMemoryStorage()
    filename = "2308_TW_v2_report_20260626_120000.html"
    keys = report_bundle_keys_for_filename(filename)
    storage.save_report(keys.html_key, b"<html></html>", content_type="text/html")
    storage.save_report(
        keys.data_key,
        json.dumps(
            {
                "snapshot_schema_version": 3,
                "ticker": "2308.TW",
                "company_name": "台達電",
                "pipeline": "v2",
                "generated_at": "2026-06-26T12:00:00+00:00",
                "conclusion_generated_at": "2026-06-26T12:00:00+00:00",
                "data_schema_version": 4,
                "source_freshness": {
                    "market_data": {"stale": True, "fetched_at": "2026-06-20T00:00:00+00:00"},
                    "financial_statements": {"stale": False, "fetched_at": "2026-06-20T00:00:00+00:00"},
                },
                "source_audit": [],
                "data_trust": {"status": "stale", "critical_failures": [], "stale_sources": ["market_data"], "notes": []},
                "data": {"ticker": "2308.TW", "company_name": "台達電", "current_price": 100.0},
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        content_type="application/json",
    )

    class FakeRefreshService:
        async def fetch_async(self, request):
            return SimpleNamespace(
                data={
                    "data_schema_version": 4,
                    "ticker": request.ticker,
                    "company_name": "台達電",
                    "current_price": 110.0,
                    "source_freshness": {
                        "market_data": {"stale": False, "fetched_at": "2026-06-27T00:00:00+00:00"},
                        "financial_statements": {"stale": False, "fetched_at": "2026-06-27T00:00:00+00:00"},
                    },
                    "source_audit": [
                        {"source": "market_data", "provider": "fake", "status": "success", "record_count": 1},
                        {"source": "financial_statements", "provider": "fake", "status": "success", "record_count": 1},
                    ],
                    "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
                }
            )

    body = asyncio.run(
        report_refresh_service.refresh_report_data_snapshot(
            filename,
            output_dir=str(tmp_path),
            refresh_service=FakeRefreshService(),
            storage=storage,
        )
    )

    saved = json.loads(storage.get_report(keys.data_key).content.decode("utf-8"))
    assert body["success"] is True
    assert saved["data_trust"]["status"] == "fresh"
    assert saved["data"]["current_price"] == 110.0
    assert storage.exists(keys.data_key) is True


def test_delete_report_files_deletes_storage_cache_and_repository(tmp_path):
    storage = InMemoryStorage()
    repository = RecordingRepository()
    lock = RecordingLock()
    filename = "2308_TW_v2_report_20260626_120000.html"
    md_filename = "2308_TW_v2_report_20260626_120000.md"
    data_filename = data_snapshot_filename_for_report(filename)
    storage.save_report(filename, b"<html></html>", content_type="text/html")
    storage.save_report(md_filename, b"# report\n", content_type="text/markdown")
    storage.save_report(data_filename, b"{}", content_type="application/json")
    report_cache = {"2308.TW": filename, "2330.TW": "other.html"}

    result = delete_report_files(
        filename,
        str(tmp_path),
        report_cache,
        repository=repository,
        report_cache_lock=lock,
        storage=storage,
    )

    assert result == {"success": True, "deleted": [filename, md_filename, data_filename]}
    assert storage.exists(filename) is False
    assert storage.exists(md_filename) is False
    assert storage.exists(data_filename) is False
    assert report_cache == {"2330.TW": "other.html"}
    assert lock.entered == 1
    assert repository.deleted == [(filename, str(tmp_path))]


def test_delete_report_files_does_not_delete_content_when_metadata_delete_fails(tmp_path):
    storage = InMemoryStorage()
    repository = FailingDeleteRepository(metadata_exists=True)
    filename = "2308_TW_v2_report_20260626_120000.html"
    storage.save_report(filename, b"<html></html>", content_type="text/html")
    report_cache = {"2308.TW": filename}

    result = delete_report_files(
        filename,
        str(tmp_path),
        report_cache,
        repository=repository,
        storage=storage,
    )

    assert result["success"] is False
    assert "metadata delete failed" in result["error"]
    assert storage.exists(filename) is True
    assert report_cache == {"2308.TW": filename}


def test_delete_report_files_can_remove_stale_metadata_when_content_is_already_missing(tmp_path):
    storage = InMemoryStorage()
    repository = RecordingRepository(metadata_exists=True)
    filename = "2308_TW_v2_report_20260626_120000.html"
    report_cache = {"2308.TW": filename}

    result = delete_report_files(
        filename,
        str(tmp_path),
        report_cache,
        repository=repository,
        storage=storage,
    )

    assert result == {"success": True, "deleted": []}
    assert repository.deleted == [(filename, str(tmp_path))]
    assert report_cache == {}


def test_report_routes_use_injected_report_storage_for_read_and_delete(tmp_path):
    storage = InMemoryStorage()
    report_cache = {"2308.TW": "2308_TW_v2_report_20260626_120000.html"}
    filename = report_cache["2308.TW"]
    storage.save_report(filename, b"<html>from storage</html>", content_type="text/html")
    storage.save_report(filename.replace(".html", ".md"), b"# report\n", content_type="text/markdown")
    storage.save_report(data_snapshot_filename_for_report(filename), b"{}", content_type="application/json")
    app = FastAPI()
    app.include_router(
        create_reports_router(
            ReportRouteDeps(
                get_output_dir=lambda: str(tmp_path),
                get_report_storage=lambda: storage,
                get_report_cache=lambda: report_cache,
                get_report_cache_lock=lambda: None,
                get_refresh_service=lambda: None,
                get_pipeline_runner=lambda: None,
                get_report_renderer=lambda: None,
                get_task_queue=lambda: None,
                run_report_rerun_job=lambda *_: "",
                create_job=lambda *_: "job",
                get_job=lambda *_: {},
                get_events_since=lambda *_: [],
                update_job=lambda *_args, **_kwargs: None,
                append_event=lambda *_args, **_kwargs: None,
                request_job_cancel=lambda *_: False,
                print_streamed_event=lambda *_: None,
                require_mutation_authorized=lambda _request: None,
            )
        )
    )
    client = TestClient(app)

    view_response = client.get(f"/api/report/{filename}")
    delete_response = client.delete(f"/api/reports/{filename}")

    assert view_response.status_code == 200
    assert "from storage" in view_response.text
    assert delete_response.status_code == 200
    assert delete_response.json()["success"] is True
    assert storage.exists(filename) is False
    assert report_cache == {}


def test_rerun_report_analysis_passes_storage_to_rerun_rendering(tmp_path, monkeypatch):
    import report_rerun_service

    filename = "2308_TW_v2_report_20260626_120000.html"
    source_snapshot = {
        "snapshot_schema_version": 3,
        "ticker": "2308.TW",
        "company_name": "台達電",
        "pipeline": "v2",
        "generated_at": "2026-06-26T12:00:00+00:00",
        "data_schema_version": 4,
        "source_freshness": {},
        "source_audit": [],
        "data_trust": {"status": "fresh", "critical_failures": [], "stale_sources": [], "notes": []},
        "data": {"ticker": "2308.TW", "company_name": "台達電"},
    }
    html_path = tmp_path / filename
    html_path.write_text("<html></html>", encoding="utf-8")
    (tmp_path / data_snapshot_filename_for_report(filename)).write_text(
        json.dumps(source_snapshot),
        encoding="utf-8",
    )

    class FakePipelineRunner:
        async def run_async(self, request):
            return SimpleNamespace(context={"ticker": "2308.TW", "data": request.data})

    class FakeReportRenderer:
        async def render_async(self, request):
            return ReportBundle(
                html="<html>rerun</html>",
                markdown="# rerun",
                data_snapshot={
                    "ticker": "2308.TW",
                    "pipeline": request.pipeline_id,
                    "data_trust": {"status": "fresh"},
                    "data": request.context["data"],
                },
            )

    monkeypatch.setattr(report_rerun_service, "time", SimpleNamespace(time=lambda: 1.0))
    storage = InMemoryStorage()

    result = asyncio_run(
        report_rerun_service.rerun_report_analysis(
            filename,
            scope="full_report",
            output_dir=str(tmp_path),
            pipeline_runner=FakePipelineRunner(),
            report_renderer=FakeReportRenderer(),
            storage=storage,
        )
    )

    from report_persistence import report_bundle_keys_for_filename

    keys = report_bundle_keys_for_filename(result["filename"])
    assert storage.get_report(keys.html_key) is not None
    assert storage.get_report(keys.md_key) is not None
    assert storage.get_report(keys.data_key) is not None


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
