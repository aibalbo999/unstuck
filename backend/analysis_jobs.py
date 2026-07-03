"""Importable analysis job entrypoints for local workers or RQ workers."""

import asyncio

from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, has_api_keys
from agent_runtime import AnalysisPipelineRunner, AnalysisRequest
from agent_runtime.retry_policy import AgentRateLimitError
from analysis_job_helpers import (
    build_data_fetch_blocking_notice,
    build_operator_audit_notice,
    stable_report_filename,
)
from analysis_job_progress import make_pipeline_progress_callback
from analysis_job_reports import render_and_persist_report
from data_fetch import FetchRequest, StockDataService
from job_store import append_event, is_job_cancel_requested, record_node_telemetry, sanitize_error_message, update_job
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
from runtime_dependencies import create_report_storage_for_output_dir, runtime_settings_for_output_dir
from temporal_memory_service import build_temporal_memory


STOCK_DATA_SERVICE = StockDataService()
PIPELINE_RUNNER = AnalysisPipelineRunner()
REPORT_RENDERER = ReportRenderer()


class AnalysisJobCancelled(Exception):
    pass


def _raise_if_cancelled(job_id: str) -> None:
    if is_job_cancel_requested(job_id):
        raise AnalysisJobCancelled("分析任務已取消。")


async def run_stock_analysis_job_async(job_id: str, ticker: str, pipeline_id: str = "v1") -> str:
    """Run the full stock analysis and persist progress events for SSE clients."""
    ticker_upper = ticker.strip().upper()
    run_id = normalize_pipeline_run_id(pipeline_id)
    pipeline_sequence = get_pipeline_run_sequence(run_id)
    run_label = get_pipeline_run_label(run_id)
    total_agents = get_pipeline_run_agent_total(run_id)
    current_thread_id = ""
    current_pipeline_label = run_label
    update_job(job_id, "running")

    def telemetry_callback(payload: dict) -> None:
        telemetry_payload = {
            **dict(payload or {}),
            "job_id": job_id,
            "ticker": ticker_upper,
            "pipeline_id": str((payload or {}).get("pipeline_id") or run_id),
        }
        record_node_telemetry(telemetry_payload)
        append_event(
            job_id,
            {
                "type": "telemetry",
                "node_name": telemetry_payload.get("node_name"),
                "model": telemetry_payload.get("model"),
                "status": telemetry_payload.get("status"),
                "latency_ms": telemetry_payload.get("latency_ms"),
                "retry_count": telemetry_payload.get("retry_count", 0),
                "quality_gate_pass": telemetry_payload.get("quality_gate_pass"),
                "error": sanitize_error_message(telemetry_payload.get("error")),
                "pipeline_id": telemetry_payload.get("pipeline_id"),
            },
        )

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
        runtime_settings = runtime_settings_for_output_dir(OUTPUT_DIR)
        report_storage = create_report_storage_for_output_dir(OUTPUT_DIR)

        for sequence_index, current_pipeline_id in enumerate(pipeline_sequence, start=1):
            _raise_if_cancelled(job_id)
            pipeline_def = get_pipeline_definition(current_pipeline_id)
            current_thread_id = f"{job_id}:{current_pipeline_id}"
            current_pipeline_label = pipeline_def["label"]
            report_filename = stable_report_filename(job_id, ticker_upper, current_pipeline_id)
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
                    thread_id=current_thread_id,
                    checkpoint_path=runtime_settings.checkpoint_path,
                    checkpoint_backend=getattr(runtime_settings, "checkpoint_backend", "sqlite"),
                    checkpoint_postgres_dsn=getattr(runtime_settings, "checkpoint_postgres_dsn", ""),
                    report_filename=report_filename,
                    telemetry_callback=telemetry_callback,
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
                filename=context.get("report_filename") or report_filename,
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
    except AgentRateLimitError as e:
        message = str(e)
        update_job(job_id, "waiting_retry", error=message)
        append_event(job_id, {
            "type": "status",
            "phase": "workflow_retry",
            "level": "warning",
            "message": "LLM API 暫時達到速率限制，任務已保留 LangGraph checkpoint，等待 RQ 延遲重試。",
            "error": message,
            "thread_id": current_thread_id,
            "pipeline_id": current_thread_id.rsplit(":", 1)[-1] if current_thread_id else run_id,
            "pipeline_label": current_pipeline_label,
        })
        raise
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
