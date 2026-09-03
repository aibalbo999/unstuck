import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_report_index_pipeline_filter_and_latest_grouping_resolve_placeholder_rows(tmp_path, monkeypatch):
    import report_index

    monkeypatch.setattr(report_index, "CACHE_DB_PATH", str(tmp_path / "cache.sqlite3"))
    older = "2330_TW_v4_report_20260620_090000.html"
    newer = "2330_TW_v4_report_20260621_090000.html"
    for filename in (older, newer):
        (tmp_path / filename).write_text("<html></html>", encoding="utf-8")
        assert report_index.upsert_report_metadata(filename, output_dir=str(tmp_path))

    with report_index._connect() as conn:
        conn.execute(
            "UPDATE reports SET pipeline_id = 'N/A' WHERE output_dir = ? AND filename = ?",
            (str(tmp_path), newer),
        )

    def raw_identity(row):
        return {"filename": row["filename"], "pipeline_id": row["pipeline_id"]}

    all_versions, all_versions_total = report_index.query_report_metadata(
        page=1,
        limit=10,
        pipeline="v4",
        include_versions=True,
        output_dir=str(tmp_path),
        sync_metadata=False,
        row_mapper=raw_identity,
    )
    latest, latest_total = report_index.query_report_metadata(
        page=1,
        limit=10,
        pipeline="v4",
        include_versions=False,
        output_dir=str(tmp_path),
        sync_metadata=False,
        row_mapper=raw_identity,
    )

    assert all_versions_total == 2
    assert {row["filename"] for row in all_versions} == {older, newer}
    assert latest_total == 1
    assert latest[0]["filename"] == newer
