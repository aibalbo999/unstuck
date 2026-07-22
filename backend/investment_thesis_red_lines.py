"""Red-line builders for investment thesis payloads."""

from __future__ import annotations

from typing import Any

from mapping_fields import safe_text


def trade_red_lines(trade_setup: dict[str, str]) -> list[dict[str, str]]:
    return [
        _red_line(f"價格觸發停損：{trade_setup.get('stop_loss') or '停損未定義'}", "致命", "取消交易、出場或重新生成 Mode D 報告"),
        _red_line("交易方向不是 Neutral，但技術、籌碼或事件任一核心證據失效", "嚴重", "降為 Neutral，不可延用原進場區間"),
        _red_line("核心催化劑過期、被否定或無法在 1-2 週內驗證", "嚴重", "移出短線任務，改列 watchlist 觀察"),
        _red_line("資料信心降級或缺少足以判斷短線波動的價格/籌碼資料", "警告", "縮小部位或等待下一次資料刷新"),
    ]


def position_red_lines(data: dict[str, Any], recommendation: str) -> list[dict[str, str]]:
    lines = [
        _red_line("目標價隱含報酬低於該建議所需風險報酬", "致命", "降級建議、降低部位或等待更佳價格"),
        _red_line("法人籌碼由支撐轉為連續派發，且價格跌破關鍵支撐", "嚴重", "停止加碼並重跑 Mode B"),
        _red_line("估值、籌碼與總經三者互相矛盾", "嚴重", "改為觀望，不把單一訊號當成交易依據"),
    ]
    if _data_trust_status(data) == "partial":
        lines.append(_red_line("資料可信度為 partial 且缺少官方資料補驗證", "警告", "降低部位與信心，不升級建議"))
    if "買" in recommendation:
        lines.append(_red_line("股價短期急漲至牛市情境上方但基本面未同步上修", "警告", "停止追價，等待回測或重新估值"))
    return lines


def contrarian_red_lines() -> list[dict[str, str]]:
    return [
        _red_line("股價放量突破防軋空停損位或關鍵壓力", "致命", "回補、停止追空並重新檢查 thesis invalidation"),
        _red_line("財測、訂單、毛利率或現金流證實多頭敘事", "致命", "撤銷泡沫假設，改跑 Mode A 或 Mode B 重新定價"),
        _red_line("做空觸發條件遲遲未出現但股價持續創高", "嚴重", "只保留觀察，不建立新的反向部位"),
        _red_line("借券、空單成本或籌碼資料不足以支持戰術做空", "警告", "降低信心，改用避開或等待觸發"),
    ]


def red_lines(data: dict[str, Any], recommendation: str) -> list[dict[str, str]]:
    lines = [
        _red_line("核心資料可信度降為 error 或關鍵財務欄位熔斷未解除", "致命", "停止使用目標價，先重跑資料校驗"),
        _red_line("連續兩季營收或自由現金流明確低於投資論文假設", "嚴重", "將論文狀態降級並重跑完整報告"),
        _red_line("護城河證據被競爭者、技術替代或客戶流失明確推翻", "嚴重", "重新評估持有理由與安全邊際"),
        _red_line("管理層誠信、重大關係人交易或財報品質出現重大疑慮", "致命", "人工審查前不得升級建議"),
    ]
    if "買" in recommendation:
        lines.append(_red_line("股價超過牛市情境且基本面沒有同步上修", "警告", "停止加碼並檢查安全邊際"))
    if _data_trust_status(data) == "partial":
        lines.append(_red_line("partial data trust 持續且無法取得官方資料補驗證", "警告", "維持灰色地帶，不提高信心分數"))
    return lines


def _red_line(condition: str, severity: str, action: str) -> dict[str, str]:
    return {"condition": condition, "severity": severity, "action": action}


def _data_trust_status(data: dict[str, Any]) -> str:
    data_trust = data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
    return safe_text(data_trust.get("status")).strip()
