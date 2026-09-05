"""Mode-specific report template profiles."""

from __future__ import annotations

from html import escape
from typing import Any

from mapping_fields import safe_dict_list, safe_mapping_dict, safe_text, safe_text_list
from pipeline_modes import normalize_pipeline_id

from .text_tokens import is_missing_text_token


_PROFILES: dict[str, dict[str, Any]] = {
    "v1": {
        "template_id": "mode_a_research",
        "template_name": "模式 A 研究型模板",
        "layout_id": "research",
        "focus_template": "includes/mode_focus/research.html.j2",
        "focus_heading": "模式 A 模板：研究優先順序",
        "focus_points": [
            "資料可信度與財務品質",
            "護城河與獲利持續性",
            "DCF / P-E 估值與多空辯論",
        ],
        "audience": "長線基本面投資人",
        "core_question": "這家公司是否值得在 3-12 個月與更長週期納入投資組合。",
        "summary_heading": "一頁式摘要",
        "decision_heading": "最終投資建議",
        "verdict_label": "最終投資建議",
        "discipline_heading": "長線投資論文與決策紀律",
        "visual_focus": ["財務趨勢", "護城河雷達", "DCF / P-E 估值", "多空辯論"],
        "reading_path": ["先看資料可信度", "再看估值與護城河", "最後看多空辯論與投資建議"],
        "show_analysis_overlays": True,
        "show_financial_charts": True,
        "section_manifest": ["analysis_overlays", "financial_charts", "agent_sections"],
        "financial_history_heading": "長線財務品質與獲利趨勢",
    },
    "v2": {
        "template_id": "mode_b_trading",
        "template_name": "模式 B 實戰交易模板",
        "layout_id": "trading",
        "focus_template": "includes/mode_focus/trading.html.j2",
        "focus_heading": "模式 B 模板：交易決策框架",
        "focus_points": [
            "進場、續抱、減碼或等待",
            "估值區間與風險報酬",
            "總經、籌碼與市場情緒",
        ],
        "audience": "主動交易與部位管理",
        "core_question": "目前是否值得進場、續抱、減碼，風險報酬是否足夠。",
        "summary_heading": "實戰交易摘要",
        "decision_heading": "實戰交易決策",
        "verdict_label": "實戰交易決策",
        "discipline_heading": "部位決策與風控紀律",
        "visual_focus": ["進出場節奏", "籌碼與情緒", "估值區間", "風險控管"],
        "reading_path": ["先看總經與籌碼", "再看估值區間", "最後決定部位與風控"],
        "show_analysis_overlays": True,
        "show_financial_charts": True,
        "section_manifest": ["market_charts", "analysis_overlays", "agent_sections", "financial_charts"],
        "market_heading": "交易價格與法人動向",
        "financial_history_heading": "交易背景與財務趨勢",
    },
    "v3": {
        "template_id": "mode_c_contrarian",
        "template_name": "模式 C 逆勢風險模板",
        "layout_id": "contrarian",
        "focus_template": "includes/mode_focus/contrarian.html.j2",
        "focus_heading": "模式 C 模板：逆勢檢查框架",
        "focus_points": [
            "泡沫敘事與財務反證",
            "估值預期與法人派發",
            "做空觸發與防軋空停損",
        ],
        "audience": "逆勢交易與風險控管",
        "core_question": "市場預期是否已脫離基本面，是否存在泡沫破裂或避險觸發點。",
        "summary_heading": "逆勢風險摘要",
        "decision_heading": "泡沫狙擊結論",
        "verdict_label": "泡沫狙擊結論",
        "discipline_heading": "逆勢論文與風控紀律",
        "visual_focus": ["泡沫證據鏈", "法證財務", "空頭反證", "做空觸發條件"],
        "reading_path": ["先看泡沫敘事", "再看財務與籌碼反證", "最後看觸發條件與停損"],
        "show_analysis_overlays": True,
        "show_financial_charts": True,
        "section_manifest": ["market_charts", "analysis_overlays", "agent_sections", "financial_charts"],
        "market_heading": "估值壓力與法人派發",
        "show_market_pe_river": True,
        "financial_history_heading": "法證財務與估值背景",
    },
    "v4": {
        "template_id": "mode_d_event_swing",
        "template_name": "模式 D 事件波段模板",
        "layout_id": "event-swing",
        "focus_template": "includes/mode_focus/event-swing.html.j2",
        "focus_heading": "模式 D 模板：事件波段執行框架",
        "focus_points": [
            "進場區間、目標與嚴格停損",
            "技術動能與主力籌碼",
            "催化事件是否仍有效",
        ],
        "audience": "短線波段與事件交易",
        "core_question": "未來短線窗口是否有明確催化、進場區間、目標與停損。",
        "summary_heading": "事件波段摘要",
        "decision_heading": "極短線交易計畫",
        "verdict_label": "短線交易方向",
        "discipline_heading": "交易計畫與風控紀律",
        "visual_focus": ["技術動能", "主力籌碼", "催化事件", "停損階梯"],
        "reading_path": ["先看交易方向", "再看進場與停損", "最後核對催化事件是否仍有效"],
        "show_analysis_overlays": False,
        "show_financial_charts": False,
        "section_manifest": ["market_charts", "agent_sections"],
        "market_heading": "短線價格與法人動能",
        "financial_history_heading": "短線市場背景",
    },
}


def get_report_template_profile(pipeline_id: Any = "v1") -> dict[str, Any]:
    profile = _PROFILES[normalize_pipeline_id(pipeline_id)]
    return {
        **profile,
        "visual_focus": list(profile["visual_focus"]),
        "reading_path": list(profile["reading_path"]),
        "focus_points": list(profile["focus_points"]),
        "section_manifest": list(profile["section_manifest"]),
    }


def decision_markdown_heading(profile: dict[str, Any]) -> str:
    heading = _text(profile.get("decision_heading"), "最終投資建議")
    if _text(profile.get("template_id"), "") == "mode_d_event_swing":
        return f"## {heading}"
    return f"## 🎯 {heading}"


def summary_markdown_heading(profile: dict[str, Any]) -> str:
    return f"## {_text(profile.get('summary_heading'), '一頁式摘要')}"


def build_mode_focus_markdown(profile: dict[str, Any], focus_context: Any = None) -> str:
    points = _text_items(profile.get("focus_points", []))
    focus = safe_mapping_dict(focus_context) or {}
    rows = safe_dict_list(focus.get("rows"))
    lines = [
        f"## {_text(profile.get('focus_heading'), '模式模板：決策框架')}",
        f"- **模板任務:** {_text(profile.get('core_question'), 'N/A')}",
        f"- **優先檢查:** {'、'.join(points) or 'N/A'}",
        f"- **決策出口:** {_text(profile.get('decision_heading'), '最終投資建議')}",
    ]
    lines.extend(
        f"- **{_text(row.get('label'), '欄位')}:** {_text(row.get('value'), '資料不足')}"
        for row in rows
    )
    return "\n".join(lines)


def build_mode_template_markdown(profile: dict[str, Any]) -> str:
    visual_focus = "、".join(_text_items(profile.get("visual_focus", [])))
    reading_path = " → ".join(_text_items(profile.get("reading_path", [])))
    return "\n".join([
        "## 報告模板與閱讀路徑",
        f"- **模板:** {_text(profile.get('template_name'), '模式模板')}",
        f"- **適用受眾:** {_text(profile.get('audience'), 'N/A')}",
        f"- **核心問題:** {_text(profile.get('core_question'), 'N/A')}",
        f"- **視覺重點:** {visual_focus or 'N/A'}",
        f"- **閱讀路徑:** {reading_path or 'N/A'}",
    ])


def build_mode_template_html(profile: dict[str, Any]) -> str:
    chips = "".join(
        f"<span>{escape(item)}</span>"
        for item in _text_items(profile.get("visual_focus", []))
    )
    path = "".join(
        f"<li>{escape(item)}</li>"
        for item in _text_items(profile.get("reading_path", []))
    )
    return f"""
        <div class="mode-template-card" data-template-id="{escape(_text(profile.get('template_id'), ''))}">
            <div class="mode-template-head">
                <span>報告模板與閱讀路徑</span>
                <strong>{escape(_text(profile.get('template_name'), '模式模板'))}</strong>
            </div>
            <div class="mode-template-body">
                <div>
                    <b>適用受眾</b>
                    <p>{escape(_text(profile.get('audience'), 'N/A'))}</p>
                </div>
                <div>
                    <b>核心問題</b>
                    <p>{escape(_text(profile.get('core_question'), 'N/A'))}</p>
                </div>
            </div>
            <div class="mode-template-chips">{chips}</div>
            <ol class="mode-template-path">{path}</ol>
        </div>
    """


def _text(value: Any, default: str) -> str:
    text = safe_text(value).strip()
    if not text or is_missing_text_token(text):
        return default
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def _text_items(value: Any) -> list[str]:
    return [text for item in safe_text_list(value) if (text := _text(item, ""))]
