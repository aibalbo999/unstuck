"""Progress-event adapter for multi-pipeline analysis jobs."""

from __future__ import annotations

def make_pipeline_progress_callback(
    *,
    job_id: str,
    pipeline_def: dict,
    current_pipeline_id: str,
    sequence_total: int,
    total_agents: int,
    completed_agent_offset: int,
    agent_count: int,
    cancel_check,
    append_event_func,
):
    state = {"pipeline_completed_count": 0, "last_event_current": completed_agent_offset}

    def progress_callback(current, total=None, name=None, phase="completed", message=None):
        cancel_check()
        raw_event = current if isinstance(current, dict) else {}
        if raw_event:
            current = raw_event.get("current", 0)
            total = raw_event.get("total", total)
            name = raw_event.get("name") or raw_event.get("message") or name
            phase = raw_event.get("phase") or ("completed" if raw_event.get("type") == "progress" else "status")
            message = raw_event.get("message", message)

        current = int(current or 0)
        local_total = int(total or agent_count)
        if phase == "completed":
            state["pipeline_completed_count"] = min(local_total, state["pipeline_completed_count"] + 1)
            calculated_current = completed_agent_offset + state["pipeline_completed_count"]
        else:
            active_increment = 1 if current and state["pipeline_completed_count"] < local_total else 0
            calculated_current = completed_agent_offset + state["pipeline_completed_count"] + active_increment

        global_current = min(total_agents, max(state["last_event_current"], calculated_current))
        state["last_event_current"] = global_current
        event_name = f"{pipeline_def['short_label']} · {name}" if sequence_total > 1 else name
        if phase == "completed":
            append_event_func(job_id, {
                "type": "progress",
                "current": global_current,
                "total": total_agents,
                "name": event_name,
                "agent_num": raw_event.get("agent_num") if raw_event else None,
                "pipeline_id": current_pipeline_id,
                "pipeline_label": pipeline_def["label"],
                "pipeline_current": current,
                "pipeline_total": local_total,
            })
            return

        detail = (
            f"{pipeline_def['short_label']} Agent {current}/{local_total} · {name}"
            if current and current <= local_total
            else f"{pipeline_def['short_label']} · {name}"
        )
        event_type = raw_event.get("type") if raw_event else "status"
        payload = {
            "type": event_type if event_type == "llm_stream_delta" else "status",
            "message": message or f"{event_name} 進行中...",
            "detail": detail,
            "current": global_current,
            "total": total_agents,
            "phase": phase,
            "level": raw_event.get("level") if raw_event else None,
            "agent_num": raw_event.get("agent_num") if raw_event else None,
            "metadata": raw_event.get("metadata") if raw_event else None,
            "pipeline_id": current_pipeline_id,
            "pipeline_label": pipeline_def["label"],
            "pipeline_current": current,
            "pipeline_total": local_total,
        }
        if event_type == "llm_stream_delta":
            payload["delta"] = raw_event.get("delta", "")
        append_event_func(job_id, payload)

    return progress_callback
