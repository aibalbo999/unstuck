"""Read separately scoped report evidence; never redate legacy screener numbers."""
import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from mapping_fields import safe_mapping_dict, safe_text, safe_dict_list
from report_history_storage import storage_for_existing_output_dir
from report_artifacts import ReportArtifactLocator
from two_week_market_eligibility import observation_readiness
from daily_candidate_review import _date
from candidate_report_identity import bound_report_ticker


def load_candidate_report_observations(candidates, items, output_dir, *, moment=None):
    moment = moment or datetime.now(ZoneInfo("Asia/Taipei"))
    storage = storage_for_existing_output_dir(output_dir, None) if output_dir else None
    locator = ReportArtifactLocator(storage) if storage else None
    by_ticker = {safe_text(i.get("ticker")).strip(): i for i in items}
    result = {}
    for candidate in candidates:
        ticker = candidate.get("ticker")
        latest = safe_mapping_dict(by_ticker.get(ticker, {}).get("latest_report")) or {}
        filename = safe_text(latest.get("filename")).strip()
        try:
            if not locator or not filename:
                raise ValueError("report_snapshot_unavailable")
            item = storage.get_report(locator.require_key(filename, kind="data"))
            raw = item.content
            snapshot = json.loads(raw)
            data = safe_mapping_dict(snapshot.get("data")) or {}
            if bound_report_ticker(snapshot, expected_ticker=ticker, metadata=latest) is None:
                raise ValueError("report_snapshot_ticker_mismatch")
            daily = safe_mapping_dict(data.get("daily_market_data")) or {}
            institution = safe_mapping_dict(data.get("institutional_trading")) or {}
            price_date = _date(daily.get("as_of"))
            last = safe_dict_list(daily.get("bars"))[-1:]
            if not price_date or not last or _date(last[0].get("date")) != price_date:
                raise ValueError("report_price_bar_date_mismatch")
            dates = [_date(d) for d in institution.get("observation_dates", [])] if isinstance(institution.get("observation_dates"), list) else []
            dates = [d for d in dates if d]
            flow_date = max(dates) if dates else None
            if price_date > moment.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat() or (flow_date and flow_date > moment.astimezone(ZoneInfo("Asia/Taipei")).date().isoformat()):
                raise ValueError("report_future_observation_date")
            readiness = observation_readiness(price_date=price_date, institutional_date=flow_date, moment=moment, ticker=ticker)
            from candidate_decision_explanation import explain_report_decision
            result[ticker] = {"decision_explanation": explain_report_decision(snapshot, latest, moment=moment), **readiness, "status":"available", "filename":filename,
                "snapshot_sha256":hashlib.sha256(raw).hexdigest(), "snapshot_generated_at":snapshot.get("generated_at"),
                "price_source":daily.get("source"), "flow_source":institution.get("source"),
                "price_adjustment_basis":daily.get("price_adjustment_basis"),
                "scope":"report snapshot only;does not date or replace screener numbers",
                "observed_close":last[0].get("close"), "observed_volume":last[0].get("volume"),
                "independent_official_verification":False, "historical_available_at_verified":False,
                "reason":"報告快照日期可讀；篩選數值維持原日期，不能用新快照替舊訊號背書。"}
        except (OSError, ValueError, TypeError, AttributeError, KeyError):
            result[ticker] = {"status":"unavailable", "filename":filename or None,
                "scope":"report snapshot only", "actionable":False,"research_only":True,
                "reason":"報告快照缺漏、格式或身分／日期不一致；保留未知，不呼叫供應商補值。"}
    return result
