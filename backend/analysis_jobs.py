"""Importable analysis job entrypoints for local workers or RQ workers."""

import asyncio

from config import API_KEY_SETUP_MESSAGE, OUTPUT_DIR, has_api_keys
from agent_runtime import AnalysisPipelineRunner, AnalysisRequest
from agent_runtime.retry_policy import AgentRateLimitError, AgentTransientError
from analysis_job_helpers import (
    build_data_fetch_blocking_notice,
    build_operator_audit_notice,
    stable_report_filename,
)
from analysis_job_progress import make_pipeline_progress_callback
from analysis_job_reports import render_and_persist_report
from analysis_job_telemetry import make_analysis_job_telemetry_callback
from analysis_job_retry import build_analysis_retry_event, prepare_analysis_retry
from analysis_job_provenance import attach_model_executions, freeze_and_record_analysis_inputs
from analysis_job_checkpoint import load_analysis_checkpoint_inputs, new_mode_input
from data_fetch import FetchRequest, StockDataService
from job_store import append_event, get_events_since, is_job_cancel_requested, terminal_job_result, update_job
from pipeline_modes import (
    get_pipeline_definition,
    get_pipeline_run_agent_total,
    get_pipeline_run_label,
    get_pipeline_run_sequence,
    normalize_pipeline_run_id,
)
from reporting import ReportRenderer
from reporting.lint import ReportLintError
from report_publication_gate import ReportPublicationBlockedError, publication_blocked_event
from quant_engine import QuantEngine
from runtime_dependencies import create_report_storage_for_output_dir, runtime_settings_for_output_dir
from temporal_memory_service import build_temporal_memory
from provider_correlation import correlate_job


STOCK_DATA_SERVICE = StockDataService()
PIPELINE_RUNNER = AnalysisPipelineRunner()
REPORT_RENDERER = ReportRenderer()


class AnalysisJobCancelled(Exception):
    pass


def _raise_if_cancelled(job_id: str) -> None:
    if is_job_cancel_requested(job_id):
        raise AnalysisJobCancelled("分析任務已取消。")


@correlate_job
async def run_stock_analysis_job_async(
    job_id: str,
    ticker: str,
    pipeline_id: str = "v1",
    force_refresh: bool = False,
) -> str:
    """Run the full stock analysis and persist progress events for SSE clients."""
    previous_result = terminal_job_result(job_id)
    if previous_result is not None:
        return previous_result
    ticker_upper = ticker.strip().upper()
    run_id = normalize_pipeline_run_id(pipeline_id)
    pipeline_sequence = get_pipeline_run_sequence(run_id)
    run_label = get_pipeline_run_label(run_id)
    total_agents = get_pipeline_run_agent_total(run_id)
    current_thread_id = ""
    current_pipeline_label = run_label
    update_job(job_id, "running")

    telemetry_callback = make_analysis_job_telemetry_callback(
        job_id=job_id,
        ticker_upper=ticker_upper,
        run_id=run_id,
        append_event_func=append_event,
    )

    try:
        if not has_api_keys():
            update_job(job_id, "error", error=API_KEY_SETUP_MESSAGE)
            append_event(job_id, {"type": "error", "message": API_KEY_SETUP_MESSAGE})
            return ""

        _raise_if_cancelled(job_id)
        runtime_settings = runtime_settings_for_output_dir(OUTPUT_DIR)
        checkpoint_inputs = await load_analysis_checkpoint_inputs(
            job_id=job_id, ticker=ticker_upper, pipeline_sequence=pipeline_sequence, settings=runtime_settings,
        )
        from nightly_analysis import prepared_input, validate_input
        from nightly_analysis_store import get_work
        nightly_work = get_work(job_id)
        nightly_data = prepared_input(job_id, ticker_upper, run_id) if nightly_work else None
        _raise_if_cancelled(job_id)
        if checkpoint_inputs:
            data = next(iter(checkpoint_inputs.values()))
            append_event(job_id, {
                "type": "status", "phase": "analysis_resume", "pipeline_id": run_id,
                "message": "已載入同一工作的原分析資料與進度；保留原取得時間、品質限制及完成結果。",
            })
        elif nightly_data is not None:
            data = nightly_data
            append_event(job_id, {"type": "status", "phase": "nightly_qualified_input",
                "session_date": nightly_work['session_date'],
                "message": "已載入門檻後核驗且綁定本交易日的新分析輸入；不重新抓取或借用舊分析。"})
        else:
            append_event(job_id, {
                "type": "status",
                "message": f"正在獲取 {ticker_upper} 財務數據...",
                "pipeline_id": run_id,
                "pipeline_label": run_label,
                "pipeline_sequence": list(pipeline_sequence),
            })
            data_result = await STOCK_DATA_SERVICE.fetch_async(
                FetchRequest.from_ticker(ticker_upper, force_refresh=force_refresh)
            )
            _raise_if_cancelled(job_id)
            data = data_result.data
            blocking_data_notice = build_data_fetch_blocking_notice(data_result)
            if blocking_data_notice:
                message = blocking_data_notice["message"]
                update_job(job_id, "error", error=message)
                append_event(job_id, {
                    "type": "error", "phase": "data_trust", "message": message,
                    "data_trust": blocking_data_notice.get("data_trust", {}),
                    "pipeline_id": run_id, "pipeline_label": run_label,
                })
                return ""
        if nightly_work:
            validate_input(nightly_work, data)
            for resumed_data in checkpoint_inputs.values():
                validate_input(nightly_work, resumed_data)
        if "error" in data:
            append_event(job_id, {"type": "status", "message": f"財務數據獲取有誤：{data['error']}，將繼續分析"})
        metrics_snapshot = data.get("quant_metrics") if checkpoint_inputs else None
        if not isinstance(metrics_snapshot, dict):
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
            mode_data = checkpoint_inputs.get(current_pipeline_id)
            if mode_data is None:
                mode_data = new_mode_input(data)
                temporal_memory = build_temporal_memory(
                    ticker_upper, output_dir=OUTPUT_DIR, current_price=data.get("current_price"),
                    pipeline_id=current_pipeline_id,
                )
                if temporal_memory:
                    mode_data["temporal_memory"] = temporal_memory
                    append_event(job_id, {"type": "status", "pipeline_id": current_pipeline_id,
                        "message": "已載入同模式上一期報告記憶，最終 Agent 將反思先前假設。"})
                freeze_and_record_analysis_inputs(job_id, current_pipeline_id, mode_data, append_event)
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
                    data=mode_data,
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
            # The graph may have repaired its input. Persist the actual basis
            # used by the report, never a discarded pre-resume fetch.
            report_data = context.get("data")
            if not isinstance(report_data, dict):
                report_data = mode_data
            update_job(job_id, "running", data_snapshot=report_data,
                       metrics_snapshot=report_data.get("quant_metrics", metrics_snapshot))
            attach_model_executions(context, get_events_since(job_id), current_pipeline_id)
            audit_notice = build_operator_audit_notice(context)

            if audit_notice["status"] == "passed_with_notes":
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
    except (ReportPublicationBlockedError, ReportLintError) as e:
        event = publication_blocked_event(
            e, thread_id=current_thread_id, pipeline_label=current_pipeline_label,
            pipeline_id=current_thread_id.rsplit(":", 1)[-1] if current_thread_id else run_id,
        )
        update_job(job_id, "error", error=event["message"])
        append_event(job_id, event)
        return ""
    except (AgentRateLimitError, AgentTransientError) as e:
        retry = prepare_analysis_retry(job_id, e)
        event = build_analysis_retry_event(e, retry)
        update_job(job_id, "waiting_retry" if retry["retry_scheduled"] else "error", error=event["error"])
        append_event(job_id, {
            **event,
            "thread_id": current_thread_id, "pipeline_label": current_pipeline_label,
            "pipeline_id": current_thread_id.rsplit(":", 1)[-1] if current_thread_id else run_id,
        })
        raise
    except Exception as e:
        message = str(e)
        update_job(job_id, "error", error=message)
        append_event(job_id, {"type": "error", "message": message})
        raise


def run_stock_analysis_job(
    job_id: str, ticker: str,
    pipeline_id: str = "v1",
    force_refresh: bool = False,
) -> str:
    """Synchronous importable wrapper for RQ and local workers."""
    from config import TASK_QUEUE_BACKEND
    if TASK_QUEUE_BACKEND == "local":
        return run_stock_analysis_job_async(job_id, ticker, pipeline_id, force_refresh)
    return asyncio.run(run_stock_analysis_job_async(job_id, ticker, pipeline_id, force_refresh))
