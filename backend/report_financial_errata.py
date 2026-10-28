"""Bounded money-unit corrections, never a replacement for research or gates."""

from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

from evidence_financial_amounts import (
    _POSTFIX, check_financial_amount, extract_financial_amounts, financial_comparison_snapshot,
)
from financial_money_claims import _AMOUNT, _SCALES, _amount_matches, _target_revenue_scope
from financial_claim_context import sentence_span


def _prior_owner_is_bound(data: dict, prefix: str) -> bool:
    """Do not discard an issuer named before a comma or field separator."""
    from source_content_selection import company_aliases
    parts = re.split(r'[，,；;：:]|[（(](?![^（）()]*[）)])', prefix)
    if len(parts) == 1:
        return True
    aliases = company_aliases(data)
    ticker = str(data.get('ticker') or '')
    own = lambda part: any(alias and alias in part for alias in aliases) or bool(ticker and ticker in part)
    has_own = any(own(part) for part in parts[:-1])
    for part in parts[:-1]:
        part = re.sub(r'^\s*[-*\d.\s]+', '', part).strip()
        if not part:
            continue
        if re.search(r'同業|同儕|其他公司|競爭(?:者|對手)', part):
            return False
        if own(part):
            continue
        if _target_revenue_scope(data, _AMOUNT.sub('', part), ''):
            continue
        if has_own and re.fullmatch(r'(?:根據|依據)[^。\n]{1,150}報導', part):
            continue
        if re.fullmatch(r'(?:根據|依據)?財務(?:資料|數據)|財務與評價方面|反證|支持證據|發現|營收與利潤結構|本業獲利與現金流挑戰|獲利品質與盈餘含金量檢視|自由現金流持續為負(?:與盈餘含金量背離)?', re.sub(r'[*`]', '', part)):
            continue
        return False
    return True


def money_unit_mismatches(text: str, snapshot: dict) -> list[dict]:
    return _money_unit_mismatches(text, financial_comparison_snapshot(snapshot))


def _money_unit_mismatches(text: str, comparison: dict) -> list[dict]:
    rows = []
    for claim in extract_financial_amounts(text, []):
        if not _prior_owner_is_bound(comparison.get('data') or {}, claim['financial_period_text']):
            continue
        prefix = re.split(r'[，,；;：:（(]', claim['financial_period_text'])[-1]
        prefix = re.sub(r'(?:quant_metrics|data|history)(?:\.[\w]+)*\s*(?:與|及|和)?', '', prefix)
        prefix = _AMOUNT.sub('', prefix)
        prefix = re.sub(r'^\s*與|與\s*$', '', prefix)
        prefix = re.sub(r'對應|雖然|儘管|顯示|基於|年度|^\s*[-*]\s*', lambda m: '年' if m[0] == '年度' else '', prefix)
        if not _target_revenue_scope(comparison.get('data') or {}, prefix, claim.get('financial_heading', '')):
            continue
        checked = check_financial_amount(claim, comparison, 1.0)
        if checked['status'] != 'mismatch':
            continue
        scale = _SCALES.get(claim['unit'].lower().removesuffix('元'), _SCALES.get(claim['unit'].lower()))
        # The series checker has already resolved every endpoint and its
        # comparison semantics. A unit-only heuristic must not erase a bound
        # violation or a wrong second endpoint from the early repair loop.
        if not scale or (not claim.get('financial_series') and
                         _amount_matches(str(claim['reported_value']), scale, checked['expected_value_raw_twd'],
                                         False, 5e6 if checked['source_unit'] == 'billion_twd' else 0)):
            continue
        rows.append({**claim, **checked})
    return rows


def _plain_line(line: str) -> str:
    from reporting.utils import clean_markdown
    from bs4 import BeautifulSoup
    return BeautifulSoup(clean_markdown(line.strip()), 'html.parser').get_text()


def financial_errata(snapshot: dict, markdown_text: str = '') -> list[dict]:
    """Make explicit display receipts; unknown original inputs yield no correction.

    Corrections are bound to a complete original text line and typed source path.
    The reader may replace that exact line only, never globally replace a number.
    """
    context = snapshot.get('rerun_context') if isinstance(snapshot.get('rerun_context'), dict) else snapshot
    analyses = context.get('analyses') if isinstance(context.get('analyses'), dict) else {}
    texts = [markdown_text, snapshot.get('_reader_original_markdown', ''), *analyses.values(),
             context.get('executive_thesis', ''), context.get('tear_sheet_summary', ''), context.get('smoothed_markdown', '')]
    rows = []; seen = set()
    comparison = financial_comparison_snapshot(snapshot)
    if not comparison.get('data'):
        return []
    for text in dict.fromkeys(text for text in texts if isinstance(text, str) and text):
        if not isinstance(text, str) or not text:
            continue
        for claim in _money_unit_mismatches(text, comparison):
            line = re.sub(r'[*`]', '', claim['raw_text']).replace('−', '-')
            matches = [match for pattern in (_AMOUNT, _POSTFIX) for match in pattern.finditer(line)
                       if match['unit'].lower() == claim['unit'].lower()
                       and match['metric'].upper() == claim['financial_metric']
                       and abs(float(match['number'].replace(',', ''))) == abs(claim['reported_value'])
                       and line[sentence_span(line, *match.span())[0]:match.start()] == claim['financial_period_text']]
            # A repeated amount with ambiguous metric binding remains an explicit
            # gate failure, not an automatic presentation rewrite.
            if len(matches) != 1:
                continue
            match = matches[0]
            precision = max(1, claim.get('financial_display_precision', 2))
            value = claim['matched_value']
            if '負' in match.group() and not match['number'].startswith(('-', '+')):
                value = abs(value)
            rendered = format(Decimal(str(value)).quantize(Decimal(1).scaleb(-precision), rounding=ROUND_HALF_UP), 'f').rstrip('0').rstrip('.')
            start, end = match.start('number'), match.end('unit')
            token = line[start:end]
            replacement = rendered + line[match.end('number'):end]
            original = _plain_line(claim['raw_text'])
            # Do not manufacture a DOM binding when Markdown changed the token.
            if original.count(token) != line.count(token):
                continue
            token_index = line[:start].count(token)
            offsets = [m.start() for m in re.finditer(re.escape(token), original)]
            if token_index >= len(offsets):
                continue
            offset = offsets[token_index]
            corrected = original[:offset] + replacement + original[offset + len(token):]
            identity = (original, token, token_index, replacement, claim['matched_path'])
            if identity in seen:
                continue
            seen.add(identity)
            rows.append({'metric': claim['financial_metric'], 'period': claim['financial_period'],
                         'currency': 'TWD', 'reported_value': claim['reported_value'],
                         'corrected_value': claim['matched_value'], 'unit': claim['unit'],
                         'source_value': claim['source_value'], 'source_unit': claim['source_unit'],
                         'source_path': claim['matched_path'], 'analysis_input_cutoff': claim['analysis_input_cutoff'],
                         'context': original, 'corrected_context': corrected,
                         'original_token': token, 'token_index': token_index, 'corrected_token': replacement})
    for context in dict.fromkeys(row['context'] for row in rows):
        group = [row for row in rows if row['context'] == context]
        operations = {}
        for row in group:
            offsets = [m.start() for m in re.finditer(re.escape(row['original_token']), context)]
            operations[offsets[row['token_index']]] = row
        corrected = context
        for offset, row in sorted(operations.items(), reverse=True):
            corrected = corrected[:offset] + row['corrected_token'] + corrected[offset + len(row['original_token']):]
        for row in group:
            row['corrected_context'] = corrected
    return rows


def correct_financial_summary(summary: str, snapshot: dict) -> str:
    if not isinstance(summary, str) or not summary:
        return ''
    result = summary
    for row in financial_errata(snapshot, summary):
        if row['context'] in result:
            result = result.replace(row['context'], row['corrected_context'])
    return result
