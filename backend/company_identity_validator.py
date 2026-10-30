"""Target-company identity validation for model outputs."""

from __future__ import annotations

import re


_PEER_WORD = re.compile(r"同業|同儕|競爭|競品|對手|可比|比較|\bpeers?\b", re.IGNORECASE)
_SENTENCE_BOUNDARY = re.compile(r"[。！？；;\n]|(?<!\d)\.(?=\s|$)")
_PEER_HEADING = re.compile(
    r"^(?:(?:[一二三四五六七八九十百0-9]+)[、.．)]\s*)?"
    r"(?:同業|同儕|可比公司|比較公司|競爭對手|peers?\b)", re.IGNORECASE)


def _local_alias_context(text, start, end):
    left = max((match.end() for match in _SENTENCE_BOUNDARY.finditer(text, 0, start)), default=0)
    right = next(_SENTENCE_BOUNDARY.finditer(text, end), None)
    return text[left:start], text[end:right.start() if right else len(text)]


def _peer_heading_at(text, position):
    headings = list(re.finditer(r"(?m)^[ \t]{0,3}#{1,6}[ \t]+([^\n]+)", text[:position]))
    if not headings:
        return False
    title = re.sub(r"[*`_]|[ \t]+#+[ \t]*$", "", headings[-1].group(1)).strip()
    return bool(_PEER_HEADING.match(title))


def _alias_renames_target(before, after, target_aliases):
    subjects = ["本公司", "本集團", "本次標的", "投資標的", "研究標的", "目標公司", "標的公司", "分析主體", "公司名稱"]
    subjects.extend(str(alias) for alias in target_aliases if alias)
    subject = "(?:" + "|".join(re.escape(value) for value in subjects) + ")"
    before = re.sub(r"[*`_]", "", before)
    after = re.sub(r"[*`_]", "", after)
    after = re.sub(r"^\s*[（(]\s*\d{4,6}(?:\.[A-Za-z]+)?\s*[）)]", "", after)
    relation = re.match(r"\s*(?:的)?(?:主要|重要|核心|最大|首要|上游|下游)?"
                        r"(?:供應商|客戶|競爭者|競爭對手|合作對象|合作夥伴|同業|比較對象|可比公司|子公司|母公司)", after)
    # Here 為 means "for" when followed by an explicit service relation.
    relation = relation or (before.rstrip().endswith("為") and re.match(r"\s*提供", after))
    if not relation and re.search(subject + r"(?:\s*[（(]\s*\d{4,6}(?:\.[A-Za-z]+)?\s*[）)])?"
                 r"\s*[（(]?\s*(?:是|為|即|就是|即為|名稱為|名稱是|名為|又稱|亦即|也就是)?\s*[:：]?\s*$", before):
        return True
    return bool(re.match(r"\s*(?:(?:是|為|即|就是|即為|亦即|也就是|作為)\s*|[（(]\s*(?:即|亦即)?\s*)" + subject + r"(?=$|[\s，,。；;：:、！？!?）)])", after))


def count_unqualified_alias(text: str, alias: str, peer_code=None, protected_aliases=()) -> int:
    """Qualify each mention within its own sentence or explicit peer section."""
    if not text or not alias:
        return 0
    protected_spans = [
        (match.start(), match.end())
        for protected_alias in protected_aliases if protected_alias
        for match in re.finditer(re.escape(protected_alias), text, flags=re.IGNORECASE)
    ]
    count = 0
    for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
        if any(start <= match.start() and match.end() <= end for start, end in protected_spans):
            continue
        before, after = _local_alias_context(text, match.start(), match.end())
        if _alias_renames_target(before, after, protected_aliases):
            count += 1
            continue
        # A nearby unrelated ticker must not qualify this name. An explicitly
        # stated code must match this exact registered peer, including its end.
        code_match = re.match(r"^[*`_\s]*[（(]\s*(\d{4,6}(?:\.[\w.-]+)?)\s*[）)]", after)
        if code_match:
            code = code_match.group(1).upper()
            valid_code = bool(peer_code) and code in {str(peer_code), f"{peer_code}.TW", f"{peer_code}.TWO"}
            if valid_code and (_PEER_WORD.search(before) or _peer_heading_at(text, match.start())):
                continue
            count += 1
            continue
        # Preserve ordinary inline '同業大亞' references, but never borrow a
        # qualifier across a sentence, newline, or heading boundary.
        if _PEER_WORD.search(before[-30:] + after[:30]):
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
    stock_id = identity.get("stock_id", ticker.replace(".TWO", "").replace(".TW", ""))
    official_name = identity.get("official_name")
    allowed_aliases = set(identity.get("allowed_aliases", []))
    forbidden_aliases = set(identity.get("forbidden_aliases", []))

    current_ticker_patterns = [
        re.escape(ticker),
        re.escape(stock_id),
        rf"{re.escape(stock_id)}\.(?:TW|TWO)",
    ]

    def alias_bound_to_current_ticker(alias: str) -> bool:
        identity_text = re.sub(r"[*`]", "", text)
        alias_re = re.escape(alias)
        for ticker_re in current_ticker_patterns:
            patterns = [
                rf"{alias_re}\s*[（(]\s*{ticker_re}",
                rf"{ticker_re}\s*[）)]?\s*{alias_re}",
            ]
            if any(re.search(pattern, identity_text, flags=re.IGNORECASE) for pattern in patterns):
                return True
        return False

    def alias_renames_current_target(alias: str) -> bool:
        protected_spans = [(match.start(), match.end())
                           for allowed in allowed_aliases if allowed
                           for match in re.finditer(re.escape(allowed), text, flags=re.IGNORECASE)]
        for match in re.finditer(re.escape(alias), text, flags=re.IGNORECASE):
            if any(start <= match.start() and match.end() <= end for start, end in protected_spans):
                continue
            if _alias_renames_target(*_local_alias_context(text, match.start(), match.end()), allowed_aliases):
                return True
        return False

    for peer in identity.get("same_industry_peers", []):
        peer_name = peer.get("stock_name", "")
        peer_code = peer.get("stock_id", "")
        if not peer_name or peer_name in allowed_aliases:
            continue
        if alias_bound_to_current_ticker(peer_name):
            issues.append(f"公司身分錯置：同業「{peer_name}」被綁定到本次標的 {ticker}。")
            continue
        if alias_renames_current_target(peer_name):
            issues.append(f"公司身分錯置：同業「{peer_name}」被稱為本次標的 {ticker}。")
            continue
        if len(peer_name) < 2:
            continue
        unqualified_count = count_unqualified_alias(
            text,
            peer_name,
            peer_code=peer_code,
            protected_aliases=allowed_aliases,
        )
        threshold = 2 if peer_name in forbidden_aliases else 4
        if unqualified_count >= threshold:
            issues.append(f"公司身分污染：同業「{peer_name}」在未標示為同業的脈絡中出現 {unqualified_count} 次。")

    for alias in identity.get("forbidden_aliases", []):
        if len(alias) < 2:
            continue
        if alias_bound_to_current_ticker(alias):
            issues.append(f"公司身分錯置：輸出將「{alias}」綁定到本次標的 {ticker}。")
            continue
        if alias_renames_current_target(alias):
            issues.append(f"公司身分錯置：輸出將「{alias}」稱為本次標的 {ticker}。")
            continue
        peer_code = next((peer.get("stock_id") for peer in identity.get("same_industry_peers", [])
                          if peer.get("stock_name") == alias), None)
        unqualified_count = count_unqualified_alias(
            text, alias, peer_code=peer_code, protected_aliases=allowed_aliases,
        )
        if unqualified_count >= 2:
            issues.append(f"公司身分污染：輸出中多次以「{alias}」作為主體，疑似套用了錯誤公司。")

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
