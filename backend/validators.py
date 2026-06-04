"""Validation and sanitization rules for model-generated stock analysis."""

from __future__ import annotations

import re
from typing import Optional

from audit_rule_engine import evaluate_configured_audit_rules


def _safe_float(value) -> Optional[float]:
    if value is None or value == "N/A":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("x", "").replace("%", "").strip()
            if not value:
                return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _relative_gap(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1.0)


def _money_text_to_billion(raw_num: str, unit: str = "") -> Optional[float]:
    value = _safe_float(raw_num)
    if value is None:
        return None
    unit = unit or ""
    if unit == "億":
        return value / 10
    if unit == "兆":
        return value * 1000
    return value


def _has_data_quality_caveat(normalized: str) -> bool:
    return any(
        word in normalized
        for word in [
            "資料品質警示",
            "口徑差異",
            "口徑不同",
            "口徑偏差",
            "口徑互斥",
            "不可直接",
            "不得直接",
            "不能直接",
            "不應直接",
            "僅列為警示",
            "僅供對照",
            "需人工複核",
            "同期間年度",
            "年度杜邦恒等式",
        ]
    )


CYCLICAL_INDUSTRY_KEYWORDS = [
    "航運",
    "海運",
    "貨櫃",
    "散裝",
    "面板",
    "顯示器",
    "LCD",
    "OLED",
    "記憶體",
    "DRAM",
    "NAND",
    "Memory",
    "Shipping",
    "Marine",
    "Display",
]


def _is_cyclical_low_pe_setup(data: dict) -> bool:
    signature = " ".join(str(data.get(key, "") or "") for key in ["company_name", "sector", "industry"])
    if not any(keyword.lower() in signature.lower() for keyword in CYCLICAL_INDUSTRY_KEYWORDS):
        return False
    pe = _safe_float(data.get("pe_ratio_raw"))
    if pe is None:
        pe = _safe_float(data.get("pe_ratio"))
    return pe is not None and 0 < pe < 5


def strip_generated_audit_sections(text: str) -> str:
    """Remove system-generated warning/audit tails before re-validating model text."""
    if not text:
        return ""
    generated_headers = [
        "\n## 系統品質檢查警示",
        "\n## 系統身分一致性警示",
        "\n## 系統最終稽核",
        "\n### 系統品質檢查警示",
        "\n### 系統身分一致性警示",
        "\n### 系統最終稽核",
    ]
    indexes = [text.find(header) for header in generated_headers if text.find(header) != -1]
    if not indexes:
        return text
    return text[:min(indexes)].rstrip()


def _extract_revenue_mentions(normalized: str) -> list[dict]:
    mentions = []
    pattern = re.compile(
        r"(?P<label>TTM|LTM|20\d{2}年|最新年度|前一年度)?"
        r"營收(?:為|=|:|：|達|約)?(?:NT\$?)?"
        r"(?P<num>\d+(?:\.\d+)?)(?P<unit>B|億|兆)?",
        re.IGNORECASE,
    )
    for match in pattern.finditer(normalized):
        value_b = _money_text_to_billion(match.group("num"), match.group("unit") or "")
        if value_b is None:
            continue
        mentions.append({
            "label": match.group("label") or "",
            "value_b": value_b,
            "start": match.start(),
        })
    return mentions


def _extract_first_money_billion(pattern: str, normalized: str) -> Optional[float]:
    match = re.search(pattern, normalized, flags=re.IGNORECASE)
    if not match:
        return None
    return _money_text_to_billion(match.group("num"), match.groupdict().get("unit") or "")


def _extract_first_percent(pattern: str, normalized: str) -> Optional[float]:
    match = re.search(pattern, normalized, flags=re.IGNORECASE)
    if not match:
        return None
    return _safe_float(match.group("num"))


def _append_deep_numeric_consistency_issues(issues: list[str], normalized: str):
    """Catch arithmetic contradictions that do not depend on a named rule."""
    revenue_mentions = _extract_revenue_mentions(normalized)
    revenue_growth_claim = _extract_first_percent(
        r"營收(?:年增率|成長率|年增|成長|增長|暴增)(?:高達|達|為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%",
        normalized,
    )
    if revenue_growth_claim is not None and len(revenue_mentions) >= 2:
        current = next((item for item in revenue_mentions if item["label"].upper() in {"TTM", "LTM"}), revenue_mentions[-1])
        base_candidates = [item for item in revenue_mentions if item is not current and item["value_b"] > 0]
        if base_candidates:
            base = base_candidates[-1] if current["start"] > base_candidates[-1]["start"] else base_candidates[0]
            expected_growth = (current["value_b"] / base["value_b"] - 1) * 100
            if abs(revenue_growth_claim - expected_growth) > max(10, abs(expected_growth) * 0.35):
                issues.append(
                    "算術一致性紅線：報告列出的營收基期與 TTM/最新營收推不出所宣稱的營收成長率；"
                    f"依文中數字約為 {expected_growth:.1f}%，不是 {revenue_growth_claim:.1f}%。"
                )

    revenue_b = next((item["value_b"] for item in revenue_mentions if item["label"].upper() in {"TTM", "LTM"}), None)
    if revenue_b is None and revenue_mentions:
        revenue_b = revenue_mentions[0]["value_b"]
    margin_pct = _extract_first_percent(r"淨利率(?:為|=|:|：|約|高達)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
    market_cap_b = _extract_first_money_billion(
        r"市值(?:為|=|:|：|約)?(?:NT\$?)?(?P<num>\d+(?:\.\d+)?)(?P<unit>B|億|兆)?",
        normalized,
    )
    pe = _extract_first_percent(
        r"(?:TTM)?(?:P/E|本益比)(?:為|=|:|：|約)?(?P<num>\d+(?:\.\d+)?)x?",
        normalized,
    )
    if revenue_b and margin_pct is not None and market_cap_b and pe and pe > 0:
        implied_income_from_margin = revenue_b * margin_pct / 100
        implied_income_from_pe = market_cap_b / pe
        if _relative_gap(implied_income_from_margin, implied_income_from_pe) > 0.25:
            issues.append(
                "估值一致性紅線：文中 TTM 營收×淨利率 推回淨利，與 市值÷P/E 推回淨利差異超過 25%；"
                "必須標示資料口徑互斥並採用校準後口徑。"
            )

    if not _has_data_quality_caveat(normalized):
        roe = _extract_first_percent(r"ROE(?:為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
        roa = _extract_first_percent(r"ROA(?:為|=|:|：|約)?(?P<num>-?\d+(?:\.\d+)?)%", normalized)
        equity_multiplier_match = re.search(
            r"權益乘數(?:為|=|:|：|約)?(?P<num>\d+(?:\.\d+)?)(?:x|倍)?",
            normalized,
            flags=re.IGNORECASE,
        )
        equity_multiplier = _safe_float(equity_multiplier_match.group("num")) if equity_multiplier_match else None
        if roe is not None and roa is not None and equity_multiplier is not None:
            implied_roe = roa * equity_multiplier
            if abs(implied_roe - roe) > max(3, abs(roe) * 0.15):
                issues.append(
                    "杜邦數值一致性紅線：文中 ROA×權益乘數 與 ROE 差距過大；"
                    "若不是同期間同口徑資料，不可作為杜邦恒等式拆解。"
                )


def validate_analysis_output(agent_num: int, text: str, data: Optional[dict] = None) -> list[str]:
    """檢查模型輸出是否踩到硬性財務邏輯紅線。"""
    issues = []
    normalized = re.sub(r"\s+", "", strip_generated_audit_sections(text or ""))
    data = data or {}

    issues.extend(
        evaluate_configured_audit_rules(
            agent_num,
            normalized,
            has_data_quality_caveat=_has_data_quality_caveat(normalized),
        )
    )

    if agent_num in (4, 7) and _is_cyclical_low_pe_setup(data):
        low_pe_bargain_claim = (
            any(word in normalized for word in ["低本益比", "本益比偏低", "P/E偏低", "PE偏低", "本益比低", "P/E低", "PE低"])
            and any(word in normalized for word in ["低估", "被低估", "便宜", "估值便宜", "買入", "上修"])
        )
        has_cycle_caveat = any(word in normalized for word in ["景氣循環", "循環股", "高PE買", "低PE賣", "獲利高峰", "谷底", "庫存循環"])
        if low_pe_bargain_claim and not has_cycle_caveat:
            issues.append(
                "景氣循環股紅線：航運、面板、記憶體等循環產業在 P/E < 5x 時，"
                "不可單靠低本益比推論低估；需先判斷是否處於獲利高峰與循環反轉風險。"
            )

    yahoo_growth = str(data.get("yahoo_revenue_growth", "")).replace("%", "").strip()
    if yahoo_growth and yahoo_growth != "N/A" and yahoo_growth in normalized:
        if any(word in normalized for word in ["營收年增率", "TTM營收成長", "TTM營收年增", "營收成長率高達"]):
            if not any(word in normalized for word in ["Yahoo近期", "季度口徑", "近期口徑", "不可直接稱為"]):
                issues.append(
                    "成長率口徑紅線：Yahoo revenueGrowth 通常是近期/季度口徑，不可直接寫成 TTM 或年度營收年增率；"
                    "請改用年度財報 YoY 或 TTM 相對最新年度 run-rate 檢查。"
                )

    provider_margin = str(data.get("profit_margin_provider", "")).replace("%", "").strip()
    calibrated_margin = str(data.get("profit_margin", "")).replace("%", "").strip()
    if provider_margin and provider_margin != "N/A" and calibrated_margin and provider_margin != calibrated_margin:
        if provider_margin in normalized and "淨利率" in normalized:
            if not any(word in normalized for word in ["Yahoo原始", "資料源對照", "口徑互斥", "不採用"]):
                issues.append(
                    "淨利率口徑紅線：Yahoo 原始 profitMargins 與 P/E/EPS 推回淨利互斥時，"
                    "正式分析必須採用校準後淨利率，原始值只能作為資料品質警示。"
                )

    _append_deep_numeric_consistency_issues(issues, normalized)

    return list(dict.fromkeys(issues))


def append_quality_warnings(agent_num: int, text: str, data: Optional[dict] = None) -> str:
    issues = validate_analysis_output(agent_num, text, data)
    if not issues:
        return text

    warning_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"{text}\n\n"
        "## 系統品質檢查警示\n"
        "以下內容觸發硬性財務邏輯檢查；閱讀本段分析時請優先採用警示所述修正口徑：\n"
        f"{warning_lines}"
    )


def _count_unqualified_alias(text: str, alias: str, peer_code=None) -> int:
    """Count suspicious alias mentions that are not clearly marked as peer comparisons."""
    if not text or not alias:
        return 0

    count = 0
    peer_tokens = []
    if peer_code:
        peer_tokens = [peer_code, f"{peer_code}.TW", f"{peer_code}.TWO"]

    peer_context_words = [
        "同業",
        "競爭",
        "競品",
        "對手",
        "可比",
        "比較",
        "peer",
        "Peers",
        "同業比較",
    ]

    for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
        window = text[max(0, match.start() - 30): min(len(text), match.end() + 30)]
        if peer_tokens and any(token in window for token in peer_tokens):
            continue
        if any(word in window for word in peer_context_words):
            continue
        count += 1
    return count


def validate_company_identity(text: str, data: dict) -> list[str]:
    """Detect target-company identity contamination before it enters later-agent context."""
    identity = data.get("company_identity", {}) or {}
    if not identity or not text:
        return []

    issues = []
    ticker = data.get("ticker", identity.get("ticker", ""))
    stock_id = identity.get("stock_id", ticker.replace(".TW", "").replace(".TWO", ""))
    official_name = identity.get("official_name")
    allowed_aliases = set(identity.get("allowed_aliases", []))
    forbidden_aliases = set(identity.get("forbidden_aliases", []))

    current_ticker_patterns = [
        re.escape(ticker),
        re.escape(stock_id),
        rf"{re.escape(stock_id)}\.(?:TW|TWO)",
    ]

    def alias_bound_to_current_ticker(alias: str) -> bool:
        alias_re = re.escape(alias)
        for ticker_re in current_ticker_patterns:
            patterns = [
                rf"{alias_re}\s*[（(]\s*{ticker_re}",
                rf"{ticker_re}\s*[）)]?\s*{alias_re}",
            ]
            if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns):
                return True
        return False

    for alias in identity.get("forbidden_aliases", []):
        if len(alias) < 2:
            continue
        if alias_bound_to_current_ticker(alias):
            issues.append(f"公司身分錯置：輸出將「{alias}」綁定到本次標的 {ticker}。")
            continue
        unqualified_count = _count_unqualified_alias(text, alias)
        if unqualified_count >= 2:
            issues.append(f"公司身分污染：輸出中多次以「{alias}」作為主體，疑似套用了錯誤公司。")

    for peer in identity.get("same_industry_peers", []):
        peer_name = peer.get("stock_name", "")
        peer_code = peer.get("stock_id", "")
        # 同業名單裡有不少兩字名稱會同時是產業普通名詞（例如「綠電」）。
        # 這類詞只適合在「代號綁定錯置」時攔截，不能單靠出現次數判定為公司身分污染。
        if not peer_name or peer_name in allowed_aliases or peer_name in forbidden_aliases:
            continue
        if alias_bound_to_current_ticker(peer_name):
            issues.append(f"公司身分錯置：同業「{peer_name}」被綁定到本次標的 {ticker}。")
            continue
        if len(peer_name) < 3:
            continue
        unqualified_count = _count_unqualified_alias(text, peer_name, peer_code=peer_code)
        if unqualified_count >= 4:
            issues.append(f"公司身分污染：同業「{peer_name}」在未標示為同業的脈絡中出現 {unqualified_count} 次。")

    if official_name and issues and official_name not in text:
        issues.append(f"公司身分缺失：輸出未使用官方中文名稱「{official_name}」。")

    return list(dict.fromkeys(issues))


def build_identity_retry_instruction(data: dict, issues: list[str]) -> str:
    """Tell the model exactly why the prior output was rejected."""
    identity = data.get("company_identity", {}) or {}
    official_name = identity.get("official_name") or data.get("company_name", data.get("ticker", "本公司"))
    ticker = data.get("ticker", identity.get("ticker", "N/A"))
    issue_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        "🚨【前一次輸出已被系統退件，請重寫】\n"
        f"退件原因：\n{issue_lines}\n"
        f"請完全重寫本段，唯一主體必須是「{official_name}（{ticker}）」；"
        "不得使用同業公司名稱作為本公司稱呼，也不得把同業商業模式、專案或新聞套用到本公司。"
    )


def append_identity_warnings(text: str, issues: list[str]) -> str:
    if not issues:
        return text
    warning_lines = "\n".join(f"- {issue}" for issue in issues)
    return (
        f"{text}\n\n"
        "## 系統身分一致性警示\n"
        "本段未通過公司身分一致性檢查，報告不應作為正式輸出：\n"
        f"{warning_lines}"
    )


REPORT_CONTENT_START_RE = re.compile(
    r"^\s*(?:#{1,4}\s+.+|(?:#{1,4}\s+)?(?:[一二三四五六七八九十]+[、.．]|執行摘要|短中長期展望|長期展望|關鍵催化因子|主要風險|最終投資決策論述|"
    r"🐂\s*多頭[：:]|🐻\s*空頭[：:]|\[護城河評分\]|\[目標股價\]|\[投資建議\]))"
)

PROMPT_LEAK_RESIDUE_RE = re.compile(
    r"(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department|BlackRock Active Investment Research Team|"
    r"Growth Equity Researcher at Fidelity|Valid parseable JSON only|No markdown code fences|Specific JSON schema|"
    r"JSON schema:|analysis_markdown|moat_scores|price_targets|Must use \"|No roleplay meta-talk|Check:\s*Did I|Past 5 years of financial trends|"
    r"Analyze the \"Economic Moat\"|Analyze the growth potential|"
    r"Growth Scenarios \(5 years\)|Professional, data-driven)",
    re.IGNORECASE,
)


def strip_prompt_preamble(text: str) -> str:
    """Drop leaked role/task setup before the first formal report section."""
    if not text:
        return ""

    if "\\n" in text and ("analysis_markdown" in text or "\\n##" in text or "\\n###" in text):
        text = text.replace("\\n", "\n")

    lines = text.splitlines()
    start_index = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if REPORT_CONTENT_START_RE.match(stripped):
            start_index = idx
            break

    if start_index and any(PROMPT_LEAK_RESIDUE_RE.search(line) for line in lines[:start_index]):
        lines = lines[start_index:]

    while lines and lines[-1].strip() in {'"', '"}', '}', '},', "```"}:
        lines.pop()

    return "\n".join(lines)


def validate_prompt_leakage(text: str) -> list[str]:
    """Return high-confidence prompt leakage findings after sanitization."""
    if not text:
        return []
    findings = []
    for pattern in [
        "Senior Analyst at Goldman Sachs",
        "Valid parseable JSON only",
        "No markdown code fences",
        "Specific JSON schema",
        "Check: Did I",
        "No roleplay meta-talk",
    ]:
        if pattern.lower() in text.lower():
            findings.append(f"輸出仍包含內部提示詞片段：{pattern}")
    return findings


def sanitize_model_output(text: str) -> str:
    """Remove prompt/scratchpad leakage before it enters reports or later-agent context."""
    if not text:
        return ""

    text = strip_prompt_preamble(text)
    leak_patterns = [
        r"^\s*(Senior Analyst at Goldman Sachs|Morgan Stanley Taiwan Research Department Financial Modeling Expert|Competitive Advantage Analyst at BlackRock|BlackRock Active Investment Research Team|Growth Equity Researcher at Fidelity|Fidelity Investments Growth Equity Researcher)\b",
        r"^\s*你好，我是(高盛|摩根士丹利|貝萊德|JP\s*摩根|富達投資|T\.?\s*Rowe|德富金融)",
        r"^\s*(Deep financial analysis of|Deep financial data analysis of|Economic Moat analysis of|.*Deep moat evaluation|.*Analyze the growth potential|Analyze the growth potential|Analyze the 5-10 year growth potential of|Financial data provided)\b",
        r"^\s*\*?\s*(Currency|Units|TTM units|Debt to Equity|Manufacturing Logic|Valuation Cross-check|Forward EPS implicit.*|FCF quality check.*|WACC|DuPont Analysis|ROE Discrepancy|Language|Unit Check|Tone|Constraint Check|First paragraph MUST|No internal monologue|Valid parseable JSON only|No markdown code fences|No extra text outside JSON|JSON schema|Specific JSON schema|analysis_markdown|moat_scores|price_targets|recommendation)\s*:",
        r"^\s*\*?\s*(Specific scoring format|Traditional Chinese|Rigorous adherence|Cross-check Forward EPS|Manufacturing logic|First paragraph MUST|No internal monologue|Valid parseable JSON only|No markdown code fences|No extra text outside JSON|JSON schema|No roleplay meta-talk|analysis_markdown|moat_scores|price_targets|recommendation)\b",
        r"^\s*\*?\s*(Observation|The Red Flag|Action|Company Profile|Financials \(Key Highlights\))\s*:",
        r"^\s*\*?\s*(Section\s+[IVX0-9]+|TAM|SAM|SOM|Estimation)\s*:",
        r"^\s*\d+\.\s*(Market Size|Key Growth Drivers|AI\s*&\s*New Tech Impact|Long-term Market Share|5-Year Growth Scenarios|Overall Growth Potential)",
        r"^\s*\*?\s*(Data|Trend|Calculation|Driver|Net Profit|Margins|Quality|Critical Check|Conversion Rate|Warning Flag|Total Debt|Net Cash Position|Valuation|Growth|Key Product|Intellectual Property|Financials|Cash Flow|Identity|Check)\s*:",
        r"^\s*(Professional, data-driven|Company Overview & Business Model|Macroeconomics & Industry Trends|Supply Chain Position & Competitive Landscape|Key Risk Factors|Analyze the \"Economic Moat\"|Analyze the growth potential)\b",
        r"\b(I must|I need to|Let's|Wait:|As a Fidelity researcher)\b",
    ]
    leak_re = re.compile("|".join(leak_patterns), re.IGNORECASE)

    kept_lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in {'"', '"}', '}', '},', "```"}:
            continue
        if leak_re.search(stripped):
            continue
        kept_lines.append(line)

    cleaned = "\n".join(kept_lines)
    cleaned = normalize_bad_number_commas(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def normalize_bad_number_commas(text: str) -> str:
    """Fix values like 1,0064.8億 -> 10,064.8億."""
    def repl(match):
        raw = f"{match.group(1)}{match.group(2)}"
        decimal = match.group(3) or ""
        return f"{int(raw):,}{decimal}"

    return re.sub(r"(?<!\d)(\d),(\d{4})(\.\d+)?(?=億)", repl, text or "")


def _parse_price_number(raw: str) -> float:
    return float(raw.replace(",", ""))


def _extract_price_numbers(text: str) -> list[float]:
    """Extract currency-like prices while preserving thousands separators."""
    number_pattern = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
    currency_matches = re.findall(rf"(?:NT\$?|\$)\s*({number_pattern})", text)
    matches = currency_matches or re.findall(number_pattern, text)
    return [_parse_price_number(match) for match in matches]
