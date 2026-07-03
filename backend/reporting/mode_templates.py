"""Mode-specific report template profiles."""

from __future__ import annotations

from html import escape
from typing import Any

from pipeline_modes import normalize_pipeline_id


_PROFILES: dict[str, dict[str, Any]] = {
    "v1": {
        "template_id": "mode_a_research",
        "template_name": "模式 A 研究型模板",
        "audience": "長線基本面投資人",
        "core_question": "這家公司是否值得在 3-12 個月與更長週期納入投資組合。",
        "summary_heading": "一頁式摘要",
        "decision_heading": "最終投資建議",
        "verdict_label": "最終投資建議",
        "visual_focus": ["財務趨勢", "護城河雷達", "DCF / P-E 估值", "多空辯論"],
        "reading_path": ["先看資料可信度", "再看估值與護城河", "最後看多空辯論與投資建議"],
    },
    "v2": {
        "template_id": "mode_b_trading",
        "template_name": "模式 B 實戰交易模板",
        "audience": "主動交易與部位管理",
        "core_question": "目前是否值得進場、續抱、減碼，風險報酬是否足夠。",
        "summary_heading": "實戰交易摘要",
        "decision_heading": "實戰交易決策",
        "verdict_label": "實戰交易決策",
        "visual_focus": ["進出場節奏", "籌碼與情緒", "估值區間", "風險控管"],
        "reading_path": ["先看總經與籌碼", "再看估值區間", "最後決定部位與風控"],
    },
    "v3": {
        "template_id": "mode_c_contrarian",
        "template_name": "模式 C 逆勢風險模板",
        "audience": "逆勢交易與風險控管",
        "core_question": "市場預期是否已脫離基本面，是否存在泡沫破裂或避險觸發點。",
        "summary_heading": "逆勢風險摘要",
        "decision_heading": "泡沫狙擊結論",
        "verdict_label": "泡沫狙擊結論",
        "visual_focus": ["泡沫證據鏈", "法證財務", "空頭反證", "做空觸發條件"],
        "reading_path": ["先看泡沫敘事", "再看財務與籌碼反證", "最後看觸發條件與停損"],
    },
    "v4": {
        "template_id": "mode_d_event_swing",
        "template_name": "模式 D 事件波段模板",
        "audience": "短線波段與事件交易",
        "core_question": "未來短線窗口是否有明確催化、進場區間、目標與停損。",
        "summary_heading": "事件波段摘要",
        "decision_heading": "極短線交易計畫",
        "verdict_label": "短線交易方向",
        "visual_focus": ["技術動能", "主力籌碼", "催化事件", "停損階梯"],
        "reading_path": ["先看交易方向", "再看進場與停損", "最後核對催化事件是否仍有效"],
    },
}


def get_report_template_profile(pipeline_id: Any = "v1") -> dict[str, Any]:
    profile = _PROFILES[normalize_pipeline_id(pipeline_id)]
    return {
        **profile,
        "visual_focus": list(profile["visual_focus"]),
        "reading_path": list(profile["reading_path"]),
    }


def decision_markdown_heading(profile: dict[str, Any]) -> str:
    heading = str(profile.get("decision_heading") or "最終投資建議")
    if profile.get("template_id") == "mode_d_event_swing":
        return f"## {heading}"
    return f"## 🎯 {heading}"


def summary_markdown_heading(profile: dict[str, Any]) -> str:
    return f"## {profile.get('summary_heading') or '一頁式摘要'}"


def build_mode_template_markdown(profile: dict[str, Any]) -> str:
    visual_focus = "、".join(str(item) for item in profile.get("visual_focus", []) if item)
    reading_path = " → ".join(str(item) for item in profile.get("reading_path", []) if item)
    return "\n".join([
        "## 報告模板與閱讀路徑",
        f"- **模板:** {profile.get('template_name', '模式模板')}",
        f"- **適用受眾:** {profile.get('audience', 'N/A')}",
        f"- **核心問題:** {profile.get('core_question', 'N/A')}",
        f"- **視覺重點:** {visual_focus or 'N/A'}",
        f"- **閱讀路徑:** {reading_path or 'N/A'}",
    ])


def build_mode_template_html(profile: dict[str, Any]) -> str:
    chips = "".join(
        f"<span>{escape(str(item))}</span>"
        for item in profile.get("visual_focus", [])
        if item
    )
    path = "".join(
        f"<li>{escape(str(item))}</li>"
        for item in profile.get("reading_path", [])
        if item
    )
    return f"""
        <div class="mode-template-card" data-template-id="{escape(str(profile.get('template_id', '')))}">
            <div class="mode-template-head">
                <span>報告模板與閱讀路徑</span>
                <strong>{escape(str(profile.get('template_name', '模式模板')))}</strong>
            </div>
            <div class="mode-template-body">
                <div>
                    <b>適用受眾</b>
                    <p>{escape(str(profile.get('audience', 'N/A')))}</p>
                </div>
                <div>
                    <b>核心問題</b>
                    <p>{escape(str(profile.get('core_question', 'N/A')))}</p>
                </div>
            </div>
            <div class="mode-template-chips">{chips}</div>
            <ol class="mode-template-path">{path}</ol>
        </div>
    """
