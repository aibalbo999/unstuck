"""AI Review Pipeline for decision-grade report certification."""

from __future__ import annotations

import json
from typing import Optional

from agent_runtime import llm_transport
from config import ACTIVE_MODEL
from prompts import get_system_prompt
from report_history_service import get_report_by_filename
from report_review_gate import write_ai_review_result, determine_verdict


# A specialized prompt for the review team
REVIEW_TEAM_SYSTEM_PROMPT = """你是 T. Rowe Price 的投資決策委員會（Investment Committee）審閱團隊。
你的任務是嚴格審閱一份已經由分析師生成的股票研究報告，決定它是否達到「投資決策依據」的等級。

你必須檢查：
1. 建議與報酬約束：12 個月目標價隱含的報酬率是否支持該買入/避免建議？
2. 佐證具體性：信心分數是否具備足夠的具體數據佐證（例如毛利率、市佔率、法說會指引），而非空泛敘述？
3. 風險考量：是否明確指出關鍵風險與情境觸發器？
4. 邏輯一致性：目標價三情境是否合理遞增？

請以 JSON 格式輸出你的審查結果，必須包含：
{
  "critical_issues": ["重大瑕疵 1", ...], // 若無請給空陣列
  "warnings": ["次要提醒 1", ...], // 若無請給空陣列
  "review_summary": "綜合審閱意見，約 50-100 字",
  "confidence_adjustment": 0 // 若信心過高，給出建議下修幅度 (例如 -1 或 -2)，合理則為 0
}
"""


async def run_ai_review_pipeline(
    filename: str,
    output_dir: str,
) -> Optional[dict]:
    """
    Run an AI review team to evaluate the generated report and determine decision-grade status.
    """
    report_data = get_report_by_filename(filename, output_dir=output_dir)
    if not report_data:
        return None

    # We extract the pure text content or structured data to send to the review team
    report_markdown = report_data.get("full_markdown", "")
    if not report_markdown:
        return None
        
    original_audit_status = report_data.get("final_audit", {}).get("status", "passed")

    prompt = (
        "請審閱以下研究報告，並給出你的 JSON 評價結果：\n\n"
        f"== 報告開始 ==\n{report_markdown[:30000]}\n== 報告結束 ==\n"
    )

    try:
        response_text = await llm_transport.generate_content_async(
            model=ACTIVE_MODEL,
            system_instruction=REVIEW_TEAM_SYSTEM_PROMPT,
            prompt=prompt,
            response_schema=None, # Ideally a defined pydantic schema for the review output
        )
        
        # Simple extraction of JSON from response
        import re
        json_match = re.search(r"```(?:json)?\n(.*?)\n```", response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1)
            
        review_result = json.loads(response_text)
        
    except Exception as e:
        review_result = {
            "critical_issues": [f"AI 審閱程序發生錯誤：{str(e)}"],
            "warnings": [],
            "review_summary": "審閱失敗",
            "confidence_adjustment": 0,
        }

    critical = review_result.get("critical_issues", [])
    warnings = review_result.get("warnings", [])
    
    verdict = determine_verdict(critical, warnings, original_audit_status)
    
    return write_ai_review_result(
        report_filename=filename,
        output_dir=output_dir,
        verdict=verdict,
        review_summary=review_result.get("review_summary", ""),
        critical_issues=critical,
        warnings=warnings,
        review_agents_used=["Investment Committee AI"],
        confidence_adjustment=review_result.get("confidence_adjustment", 0),
        raw_agent_outputs={"review_team": response_text if 'response_text' in locals() else ""},
    )
