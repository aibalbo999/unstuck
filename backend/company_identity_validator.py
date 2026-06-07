"""Target-company identity validation for model outputs."""

from __future__ import annotations

import re


def count_unqualified_alias(text: str, alias: str, peer_code=None) -> int:
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
        unqualified_count = count_unqualified_alias(text, alias)
        if unqualified_count >= 2:
            issues.append(f"公司身分污染：輸出中多次以「{alias}」作為主體，疑似套用了錯誤公司。")

    for peer in identity.get("same_industry_peers", []):
        peer_name = peer.get("stock_name", "")
        peer_code = peer.get("stock_id", "")
        if not peer_name or peer_name in allowed_aliases or peer_name in forbidden_aliases:
            continue
        if alias_bound_to_current_ticker(peer_name):
            issues.append(f"公司身分錯置：同業「{peer_name}」被綁定到本次標的 {ticker}。")
            continue
        if len(peer_name) < 3:
            continue
        unqualified_count = count_unqualified_alias(text, peer_name, peer_code=peer_code)
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


_count_unqualified_alias = count_unqualified_alias
