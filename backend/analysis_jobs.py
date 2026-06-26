"""Importable analysis job entrypoints for local workers or RQ workers."""

import asyncio

from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, has_api_keys
from agent_runtime import AnalysisPipelineRunner, AnalysisRequest
from analysis_job_progress import make_pipeline_progress_callback
from analysis_job_reports import render_and_persist_report
from data_fetch import FetchRequest, StockDataService
from job_store import append_event, is_job_cancel_requested, update_job
from pipeline_modes import (
    get_pipeline_definition,
    get_pipeline_run_agent_total,
    get_pipeline_run_label,
    get_pipeline_run_sequence,
    normalize_pipeline_run_id,
)
from reporting import ReportRenderer
from reporting.lint import ReportLintError
from quant_engine import QuantEngine
from runtime_dependencies import create_report_storage_for_output_dir
from temporal_memory_service import build_temporal_memory


STOCK_DATA_SERVICE = StockDataService()
PIPELINE_RUNNER = AnalysisPipelineRunner()
REPORT_RENDERER = ReportRenderer()


class AnalysisJobCancelled(Exception):
    pass


def _raise_if_cancelled(job_id: str) -> None:
    if is_job_cancel_requested(job_id):
        raise AnalysisJobCancelled("分析任務已取消。")


def build_data_fetch_blocking_notice(data_result) -> dict | None:
    """Return a terminal notice when core data is too weak for model analysis."""
    data = data_result.data if isinstance(getattr(data_result, "data", None), dict) else {}
    trust = (
        data_result.data_trust
        if isinstance(getattr(data_result, "data_trust", None), dict)
        else data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
    )
    trust_status = str(trust.get("status") or "unknown")
    has_market_or_financials = bool(
        data.get("current_price")
        or data.get("market_cap_raw")
        or data.get("years")
        or data.get("revenue_history")
    )
    has_unusable_error_payload = bool(data.get("error")) and not has_market_or_financials

    if trust_status == "error":
        return {
            "message": "核心市場或財報來源異常，且沒有足夠可用資料；已停止本次分析，請稍後重試或檢查資料來源設定。",
            "data_trust": trust,
        }
    if has_unusable_error_payload:
        return {
            "message": f"財務資料獲取失敗且沒有可用核心資料：{data.get('error')}",
            "data_trust": trust,
        }
    return None


def build_operator_audit_notice(context: dict) -> dict:
    """Summarize final audit state for progress events and UI notices."""
    audit = context.get("final_audit", {}) or {}
    critical = list(audit.get("critical", []) or [])
    blocking = [
        issue for issue in (context.get("blocking_issues", []) or [])
        if issue not in critical
    ]
    warnings = list(audit.get("warnings", []) or [])
    corrections = list(audit.get("corrections", []) or [])
    repair_log = list(context.get("audit_repair_log", []) or [])

    if critical or blocking:
        issues = [*critical[:5], *blocking[:3]]
        first_issue = issues[0] if issues else "最終稽核仍有異常"
        return {
            "status": "needs_attention",
            "message": f"最終稽核仍有異常，報告已保留並標示提醒：{first_issue}",
            "issues": issues,
            "repair_log": repair_log[:5],
        }

    if warnings or corrections or repair_log:
        details = [*warnings[:3], *corrections[:3], *repair_log[:3]]
        return {
            "status": "passed_with_notes",
            "message": "最終稽核已通過；系統曾自動修復或套用非阻斷校正。",
            "issues": details,
            "repair_log": repair_log[:5],
        }

    return {"status": "passed", "message": "最終稽核已通過。", "issues": [], "repair_log": []}


async def run_stock_analysis_job_async(job_id: str, ticker: str, pipeline_id: str = "v1") -> str:
    """Run the full stock analysis and persist progress events for SSE clients."""
    ticker_upper = ticker.strip().upper()
    run_id = normalize_pipeline_run_id(pipeline_id)
    pipeline_sequence = get_pipeline_run_sequence(run_id)
    run_label = get_pipeline_run_label(run_id)
    total_agents = get_pipeline_run_agent_total(run_id)
    update_job(job_id, "running")

    try:
        if not has_api_keys():
            update_job(job_id, "error", error=API_KEY_SETUP_MESSAGE)
            append_event(job_id, {"type": "error", "message": API_KEY_SETUP_MESSAGE})
            return ""

        _raise_if_cancelled(job_id)
        append_event(job_id, {
            "type": "status",
            "message": f"正在獲取 {ticker_upper} 財務數據...",
            "pipeline_id": run_id,
            "pipeline_label": run_label,
            "pipeline_sequence": list(pipeline_sequence),
        })
        data_result = await STOCK_DATA_SERVICE.fetch_async(FetchRequest.from_ticker(ticker_upper))
        _raise_if_cancelled(job_id)
        data = data_result.data
        blocking_data_notice = build_data_fetch_blocking_notice(data_result)
        if blocking_data_notice:
            message = blocking_data_notice["message"]
            update_job(job_id, "error", error=message)
            append_event(job_id, {
                "type": "error",
                "phase": "data_trust",
                "message": message,
                "data_trust": blocking_data_notice.get("data_trust", {}),
                "pipeline_id": run_id,
                "pipeline_label": run_label,
            })
            return ""
        if "error" in data:
            append_event(job_id, {"type": "status", "message": f"財務數據獲取有誤：{data['error']}，將繼續分析"})
        temporal_memory = build_temporal_memory(
            ticker_upper,
            output_dir=OUTPUT_DIR,
            current_price=data.get("current_price"),
        )
        if temporal_memory:
            data["temporal_memory"] = temporal_memory
            append_event(job_id, {"type": "status", "message": "已載入上一期報告記憶，最終 Agent 將強制反思先前假設。"})
            
        metrics_snapshot = QuantEngine.compute_all(data)
        data["quant_metrics"] = metrics_snapshot
        if metrics_snapshot.get("fallback_fields"):
            data["quant_metrics"]["__has_fallback"] = True
        
        # Persist snapshots to db
        update_job(job_id, "running", data_snapshot=data, metrics_snapshot=metrics_snapshot)

        reports = []
        completed_agent_offset = 0
        sequence_total = len(pipeline_sequence)
        report_storage = create_report_storage_for_output_dir(OUTPUT_DIR)

        for sequence_index, current_pipeline_id in enumerate(pipeline_sequence, start=1):
            _raise_if_cancelled(job_id)
            pipeline_def = get_pipeline_definition(current_pipeline_id)
            agent_count = len(pipeline_def["agents"])
            append_event(job_id, {
                "type": "status",
                "message": f"開始執行 {pipeline_def['label']}（{sequence_index}/{sequence_total}，{agent_count} 位 Agent）...",
                "pipeline_id": current_pipeline_id,
                "pipeline_label": pipeline_def["label"],
                "pipeline_index": sequence_index,
                "pipeline_total": sequence_total,
                "agent_total": total_agents,
            })
            append_event(job_id, {
                "type": "pipeline_start",
                "message": f"開始第 {sequence_index}/{sequence_total} 段：{pipeline_def['label']}",
                "pipeline_id": current_pipeline_id,
                "pipeline_label": pipeline_def["label"],
                "pipeline_index": sequence_index,
                "pipeline_total": sequence_total,
                "agent_offset": completed_agent_offset,
                "agent_total": total_agents,
            })

            progress_callback = make_pipeline_progress_callback(
                job_id=job_id,
                pipeline_def=pipeline_def,
                current_pipeline_id=current_pipeline_id,
                sequence_total=sequence_total,
                total_agents=total_agents,
                completed_agent_offset=completed_agent_offset,
                agent_count=agent_count,
                cancel_check=lambda: _raise_if_cancelled(job_id),
                append_event_func=append_event,
            )

            analysis_result = await PIPELINE_RUNNER.run_async(
                AnalysisRequest(
                    data=dict(data),
                    progress_callback=progress_callback,
                    pipeline_id=current_pipeline_id,
                    cancel_check=lambda: _raise_if_cancelled(job_id),
                )
            )
            _raise_if_cancelled(job_id)
            context = analysis_result.context
            audit_notice = build_operator_audit_notice(context)

            if audit_notice["status"] == "needs_attention":
                append_event(job_id, {
                    "type": "status",
                    "message": audit_notice["message"],
                    "pipeline_id": current_pipeline_id,
                    "pipeline_label": pipeline_def["label"],
                })
            elif audit_notice["status"] == "passed_with_notes":
                append_event(job_id, {
                    "type": "status",
                    "message": audit_notice["message"],
                    "pipeline_id": current_pipeline_id,
                    "pipeline_label": pipeline_def["label"],
                })

            report_event = await render_and_persist_report(
                job_id=job_id,
                ticker_upper=ticker_upper,
                current_pipeline_id=current_pipeline_id,
                pipeline_def=pipeline_def,
                sequence_index=sequence_index,
                sequence_total=sequence_total,
                context=context,
                audit_notice=audit_notice,
                renderer=REPORT_RENDERER,
                cancel_check=lambda: _raise_if_cancelled(job_id),
                append_event_func=append_event,
                output_dir=OUTPUT_DIR,
                storage=report_storage,
            )
            reports.append(report_event)
            append_event(job_id, report_event)
            completed_agent_offset += agent_count

        _raise_if_cancelled(job_id)
        final_report = reports[-1] if reports else {}
        final_filename = final_report.get("filename", "")
        final_pipeline_id = final_report.get("pipeline_id", pipeline_sequence[-1])
        final_audit = final_report.get("audit", {"status": "passed", "message": "最終稽核已通過。", "issues": []})

        update_job(job_id, "done", filename=final_filename)
        append_event(job_id, {
            "type": "done",
            "filename": final_filename,
            "filenames": [report["filename"] for report in reports],
            "reports": reports,
            "audit": final_audit,
            "pipeline_id": run_id,
            "pipeline_label": run_label,
            "pipeline_sequence": list(pipeline_sequence),
            "last_pipeline_id": final_pipeline_id,
        })
        return final_filename

    except AnalysisJobCancelled as e:
        message = str(e)
        update_job(job_id, "cancelled", error=message)
        append_event(job_id, {"type": "error", "phase": "cancelled", "level": "warning", "message": message})
        return ""
    except ReportLintError as e:
        message = f"錯誤：{str(e)}"
        update_job(job_id, "error", error=message)
        append_event(job_id, {"type": "error", "message": message})
        return ""
    except Exception as e:
        message = str(e)
        update_job(job_id, "error", error=message)
        append_event(job_id, {"type": "error", "message": message})
        raise


def run_stock_analysis_job(job_id: str, ticker: str, pipeline_id: str = "v1") -> str:
    """Synchronous importable wrapper for RQ and local workers."""
    from config import TASK_QUEUE_BACKEND
    if TASK_QUEUE_BACKEND == "local":
        return run_stock_analysis_job_async(job_id, ticker, pipeline_id)
    return asyncio.run(run_stock_analysis_job_async(job_id, ticker, pipeline_id))
