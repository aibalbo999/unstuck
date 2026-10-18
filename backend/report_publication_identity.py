"""Distinguish archived-analysis validation from a new forecast publication."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def publication_identity(payload: dict) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    replay = payload.get("saved_analysis_replay")
    replay = replay if isinstance(replay, dict) else {}
    explicit = payload.get("publication_identity")
    explicit = explicit if isinstance(explicit, dict) else {}
    is_replay = bool(replay) or explicit.get("kind") == "saved_analysis_replay"
    repair = payload.get("saved_data_repair_validation")
    repair = repair if isinstance(repair, dict) else {}
    is_repair = bool(repair) or explicit.get("kind") == "saved_data_repair_validation"
    from memo_output_completion import incomplete_memo_roles
    is_partial = bool(incomplete_memo_roles(payload)) or explicit.get("kind") == "partial_analysis"
    raw_data = payload.get("data")
    data = dict(raw_data) if isinstance(raw_data, dict) else {}
    raw_market = data.get("daily_market_data")
    market_as_of = dict.get(raw_market, "as_of") if isinstance(raw_market, dict) else None
    return {
        "schema_version": "report-publication-identity:v1",
        "kind": "saved_analysis_replay" if is_replay else "partial_analysis" if is_partial else "saved_data_repair_validation" if is_repair else "forecast",
        "prediction_eligible": not (is_replay or is_partial or is_repair),
        "source_filename": replay.get("source_filename") or repair.get("source_filename") or explicit.get("source_filename") or "",
        "analysis_generated_at": (replay.get("source_conclusion_generated_at") or explicit.get("analysis_generated_at") or payload.get("conclusion_generated_at") or "") if is_replay else payload.get("conclusion_generated_at") or payload.get("generated_at") or "",
        "analysis_input_cutoff": replay.get("source_analysis_input_cutoff") or explicit.get("analysis_input_cutoff") or data.get("analysis_input_cutoff") or "",
        "published_at": payload.get("publication_generated_at") or explicit.get("published_at") or payload.get("generated_at") or "",
        "market_as_of": replay.get("market_as_of") or explicit.get("market_as_of") or market_as_of or "",
    }


_SNAPSHOT_NOT_PROVIDED = object()


def read_report_publication_snapshot(report: dict, output_dir: str, *, storage=None, locator=None):
    """Read the canonical data once; callers may reuse it for identity and setup."""
    from report_artifacts import ReportArtifactLocator
    from report_history_storage import storage_for_existing_output_dir
    storage = storage if storage is not None else storage_for_existing_output_dir(output_dir, None)
    if storage is None:
        return None
    locator = locator if locator is not None else ReportArtifactLocator(storage)
    key = locator.existing_key(str(report.get("filename") or ""), kind="data")
    if key:
        import json
        item = storage.get_report(key)
        if item:
            try:
                return json.loads(item.content.decode("utf-8"))
            except (UnicodeDecodeError, ValueError, TypeError):
                # Existing quality/parse gates own corrupt snapshot handling.
                pass
    return None


def read_report_publication_identity(report: dict, output_dir: str, *, snapshot=_SNAPSHOT_NOT_PROVIDED) -> dict:
    # Report lists carry an identity derived from the canonical snapshot.
    if isinstance(report.get("publication_identity"), dict):
        return publication_identity(report)
    if snapshot is _SNAPSHOT_NOT_PROVIDED:
        snapshot = read_report_publication_snapshot(report, output_dir)
    return publication_identity(snapshot if snapshot is not None else report)


def replay_context(context: dict, published_at: str) -> dict:
    identity = publication_identity(context)
    if identity["kind"] == "saved_data_repair_validation":
        return {**context, "publication_generated_at": published_at,
                "decision_validity_status": identity["kind"],
                "publication_identity": {**identity, "published_at": published_at}}
    if identity["kind"] != "saved_analysis_replay":
        return context
    return {**context, "conclusion_generated_at": identity["analysis_generated_at"],
            "publication_generated_at": published_at, "decision_validity_status": "saved_analysis_replay",
            "publication_identity": {**identity, "published_at": published_at}}


def _taipei(value: str) -> str:
    try:
        moment = datetime.fromisoformat(value)
        if moment.tzinfo:
            return moment.astimezone(ZoneInfo("Asia/Taipei")).strftime("%Y-%m-%d %H:%M 台北時間")
    except (ValueError, TypeError):
        pass
    return str(value or "未保存，不能推定為發布時間")


def replay_notice(payload: dict) -> str:
    identity = publication_identity(payload)
    if identity["prediction_eligible"]:
        return ""
    if identity["kind"] == "partial_analysis":
        from memo_output_completion import incomplete_memo_notice
        return incomplete_memo_notice(payload) or "分析未完整：不能視為完整有效的新預測，不納入決策追蹤或績效觀察母體。"
    if identity["kind"] == "saved_data_repair_validation":
        return ("保存資料修復驗證：本次重新呼叫模型，但沿用原保存資料，未取得新的市場觀測。"
                "不納入預測追蹤或績效母體。"
                f"本次模型分析：{_taipei(identity["analysis_generated_at"])}；"
                f"原資料輸入截止：{_taipei(identity["analysis_input_cutoff"])}；行情觀測日：{identity["market_as_of"] or "未保存"}。")
    return ("保存分析驗證重播：未產生新模型預測，不納入決策追蹤或績效觀察母體。"
            f"原分析：{_taipei(identity['analysis_generated_at'])}；"
            f"原輸入截止：{_taipei(identity['analysis_input_cutoff'])}；"
            f"驗證發布：{_taipei(identity['published_at'])}；行情觀測日：{identity['market_as_of'] or '未保存'}。")


def non_prediction_reason(identity):
    if identity.get('kind') == 'saved_data_repair_validation':
        return 'saved_data_repair_validation_not_prediction'
    return 'partial_analysis_not_prediction' if identity.get('kind') == 'partial_analysis' else 'saved_analysis_replay_not_prediction'
