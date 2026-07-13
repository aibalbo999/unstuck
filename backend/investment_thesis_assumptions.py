"""Assumption and red-line builders for investment thesis payloads."""

from __future__ import annotations

from typing import Any

from investment_thesis_common import chip_line, first_mapping_value, trade_direction_label
from mapping_fields import safe_dict_list, safe_text


def trade_core_assumptions(trade_setup: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "assumption": "交易方向仍由技術、籌碼與事件共同支持",
            "validation": f"目前方向為 {trade_direction_label(trade_setup.get('trade_direction'))}；若三者分歧，回到 Neutral",
            "frequency": "每日收盤後",
            "status": "active",
        },
        {
            "assumption": "進場區間仍有效",
            "validation": f"只在 {trade_setup.get('entry_zone') or '有效進場區間'} 附近等待觸發，不追價",
            "frequency": "盤中/收盤",
            "status": "active",
        },
        {
            "assumption": "停損優先於目標價",
            "validation": f"停損條件：{trade_setup.get('stop_loss') or '尚未定義，需補齊後才可使用'}",
            "frequency": "即時",
            "status": "active",
        },
        {
            "assumption": "催化事件仍在 1-2 週窗口內可驗證",
            "validation": trade_setup.get("core_catalyst") or "近期催化資料不足，應降低交易信心",
            "frequency": "事件前後",
            "status": "active",
        },
    ]


def trade_red_lines(trade_setup: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "condition": f"價格觸發停損：{trade_setup.get('stop_loss') or '停損未定義'}",
            "severity": "致命",
            "action": "取消交易、出場或重新生成 Mode D 報告",
        },
        {
            "condition": "交易方向不是 Neutral，但技術、籌碼或事件任一核心證據失效",
            "severity": "嚴重",
            "action": "降為 Neutral，不可延用原進場區間",
        },
        {
            "condition": "核心催化劑過期、被否定或無法在 1-2 週內驗證",
            "severity": "嚴重",
            "action": "移出短線任務，改列 watchlist 觀察",
        },
        {
            "condition": "資料信心降級或缺少足以判斷短線波動的價格/籌碼資料",
            "severity": "警告",
            "action": "縮小部位或等待下一次資料刷新",
        },
    ]


def core_assumptions(
    data: dict[str, Any],
    moat_scores: dict[str, Any],
    price_targets: dict[str, Any],
    recommendation: dict[str, Any],
) -> list[dict[str, str]]:
    assumptions = [
        {
            "assumption": "核心營收與獲利不惡化",
            "validation": "追蹤季營收、TTM 淨利與自由現金流是否延續報告假設",
            "frequency": "每季",
            "status": "active",
        },
        {
            "assumption": "護城河沒有被同業明確突破",
            "validation": f"追蹤整體護城河分數 {_text(moat_scores.get('整體護城河'))} 與競爭證據",
            "frequency": "每半年",
            "status": "active",
        },
        {
            "assumption": "估值仍落在三情境可解釋區間",
            "validation": f"熊/基/牛情境：{_scenario_summary(price_targets)}",
            "frequency": "每次重跑報告",
            "status": "active",
        },
    ]
    if safe_dict_list(data.get("recent_catalysts")):
        assumptions.append({
            "assumption": "近期催化劑能轉化為可驗證營運數據",
            "validation": "追蹤催化事件後的月營收、訂單或毛利率變化",
            "frequency": "事件後",
            "status": "active",
        })
    if first_mapping_value(recommendation, "建議"):
        assumptions.append({
            "assumption": "最終建議與目標價沒有和後續資料脫鉤",
            "validation": "由 decision tracking 檢查 3/6/12 個月 ROI 與命中率",
            "frequency": "3/6/12 個月",
            "status": "active",
        })
    return assumptions


def position_core_assumptions(
    data: dict[str, Any],
    price_targets: dict[str, Any],
    recommendation: dict[str, Any],
) -> list[dict[str, str]]:
    target_3m = first_mapping_value(recommendation, "3個月") or "N/A"
    target_12m = first_mapping_value(recommendation, "12個月") or _text(price_targets.get("基本情境"))
    return [
        {
            "assumption": "短中期風險報酬仍可接受",
            "validation": f"3 個月參考 {target_3m}，12 個月參考 {target_12m}；若報酬不足需降級或等待",
            "frequency": "每次重跑報告",
            "status": "active",
        },
        {
            "assumption": "籌碼與情緒沒有明確轉弱",
            "validation": chip_line(data),
            "frequency": "每日或每週",
            "status": "active",
        },
        {
            "assumption": "估值區間仍能約束部位大小",
            "validation": f"熊/基/牛情境：{_scenario_summary(price_targets)}",
            "frequency": "每次重大價格變動後",
            "status": "active",
        },
        {
            "assumption": "結論沒有和資料可信度或 final audit 警示脫鉤",
            "validation": "若出現資料降級、建議/報酬矛盾或來源衝突，先降低信心",
            "frequency": "每次資料刷新",
            "status": "active",
        },
    ]


def position_red_lines(data: dict[str, Any], recommendation: str) -> list[dict[str, str]]:
    lines = [
        {
            "condition": "目標價隱含報酬低於該建議所需風險報酬",
            "severity": "致命",
            "action": "降級建議、降低部位或等待更佳價格",
        },
        {
            "condition": "法人籌碼由支撐轉為連續派發，且價格跌破關鍵支撐",
            "severity": "嚴重",
            "action": "停止加碼並重跑 Mode B",
        },
        {
            "condition": "估值、籌碼與總經三者互相矛盾",
            "severity": "嚴重",
            "action": "改為觀望，不把單一訊號當成交易依據",
        },
    ]
    if _data_trust_status(data) == "partial":
        lines.append({
            "condition": "資料可信度為 partial 且缺少官方資料補驗證",
            "severity": "警告",
            "action": "降低部位與信心，不升級建議",
        })
    if "買" in recommendation:
        lines.append({
            "condition": "股價短期急漲至牛市情境上方但基本面未同步上修",
            "severity": "警告",
            "action": "停止追價，等待回測或重新估值",
        })
    return lines


def _text(value: Any, default: str = "N/A") -> str:
    text = safe_text(value).strip()
    return text or default


def _scenario_summary(price_targets: dict[str, Any]) -> str:
    return " / ".join(
        _text(price_targets.get(key))
        for key in ("熊市情境", "基本情境", "牛市情境")
    )


def contrarian_core_assumptions(crash_trigger: str, stop_condition: str) -> list[dict[str, str]]:
    return [
        {
            "assumption": "泡沫敘事仍未被基本面證實",
            "validation": "追蹤營收、毛利率、Forward EPS 與估值分位是否能支撐市場期待",
            "frequency": "每次財報或月營收後",
            "status": "active",
        },
        {
            "assumption": "財務與籌碼反證仍成立",
            "validation": "追蹤 FCF 品質、法人派發、借券/融券與同業相對指標",
            "frequency": "每週",
            "status": "active",
        },
        {
            "assumption": "做空或避險必須等待可驗證觸發",
            "validation": crash_trigger or "尚未形成具體觸發，不能只因估值高就追空",
            "frequency": "事件前後",
            "status": "active",
        },
        {
            "assumption": "防軋空與 thesis invalidation 條件未被觸發",
            "validation": stop_condition or "若基本面改善、股價突破風控位或籌碼轉強，需回補或暫停空方假設",
            "frequency": "每日收盤後",
            "status": "active",
        },
    ]


def contrarian_red_lines() -> list[dict[str, str]]:
    return [
        {
            "condition": "股價放量突破防軋空停損位或關鍵壓力",
            "severity": "致命",
            "action": "回補、停止追空並重新檢查 thesis invalidation",
        },
        {
            "condition": "財測、訂單、毛利率或現金流證實多頭敘事",
            "severity": "致命",
            "action": "撤銷泡沫假設，改跑 Mode A 或 Mode B 重新定價",
        },
        {
            "condition": "做空觸發條件遲遲未出現但股價持續創高",
            "severity": "嚴重",
            "action": "只保留觀察，不建立新的反向部位",
        },
        {
            "condition": "借券、空單成本或籌碼資料不足以支持戰術做空",
            "severity": "警告",
            "action": "降低信心，改用避開或等待觸發",
        },
    ]


def red_lines(data: dict[str, Any], recommendation: str) -> list[dict[str, str]]:
    lines = [
        {
            "condition": "核心資料可信度降為 error 或關鍵財務欄位熔斷未解除",
            "severity": "致命",
            "action": "停止使用目標價，先重跑資料校驗",
        },
        {
            "condition": "連續兩季營收或自由現金流明確低於投資論文假設",
            "severity": "嚴重",
            "action": "將論文狀態降級並重跑完整報告",
        },
        {
            "condition": "護城河證據被競爭者、技術替代或客戶流失明確推翻",
            "severity": "嚴重",
            "action": "重新評估持有理由與安全邊際",
        },
        {
            "condition": "管理層誠信、重大關係人交易或財報品質出現重大疑慮",
            "severity": "致命",
            "action": "人工審查前不得升級建議",
        },
    ]
    if "買" in recommendation:
        lines.append({
            "condition": "股價超過牛市情境且基本面沒有同步上修",
            "severity": "警告",
            "action": "停止加碼並檢查安全邊際",
        })
    if _data_trust_status(data) == "partial":
        lines.append({
            "condition": "partial data trust 持續且無法取得官方資料補驗證",
            "severity": "警告",
            "action": "維持灰色地帶，不提高信心分數",
        })
    return lines


def _data_trust_status(data: dict[str, Any]) -> str:
    data_trust = data.get("data_trust", {}) if isinstance(data.get("data_trust"), dict) else {}
    return safe_text(data_trust.get("status")).strip()
