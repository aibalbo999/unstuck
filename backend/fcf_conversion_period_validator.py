"""Reject explicit annual-tool citations relabeled as TTM FCF conversion.

This does not calculate a TTM ratio or infer source reuse from equal numbers.
Unbound source, issuer, period and hypothetical claims remain unassessed here.
"""
from __future__ import annotations

import math
import re
import unicodedata

from financial_claim_context import is_actual_claim
from financial_money_claims import _target_revenue_scope
from output_sanitizer import strip_generated_audit_sections

_TAG = '§ANNUALFCF§'
_METRIC = r'(?:FCF|自由現金流(?:量)?)(?:轉換率|conversion(?:ratio|rate))'
_CLAIM = re.compile(_METRIC + r'(?:偏低|偏高)?(?:為|約為|約|達|僅|是|[:：=])*'
                    r'(?P<number>[+-]?\d+(?:\.\d+)?)%', re.I)
_TTM = re.compile(r'TTM|LTM|近(?:12|十二)(?:個)?月', re.I)
_PERIOD = re.compile(_TTM.pattern + r'|(?:最新|最近)(?:完整)?年度|20\d{2}年(?:度)?|年度|全年', re.I)
_MEASURE = re.compile(r'FCF|自由現金流|淨利率|淨利|營收|ROE|ROA|WACC|毛利率|轉換率', re.I)
_SOURCE_NOTE = re.compile(r'\((?:來源|計算依據|source)[:：][^()]{1,1200}\)', re.I)
_ERROR = re.compile(r'誤寫|誤稱|錯寫|錯稱|錯誤示例|錯誤範例|錯誤說法|更正前|不採用|不可採用')
_ISSUE = ('FCF 轉換率期間紅線：明示的 TTM／LTM 轉換率引用了 '
          'latest_fcf_conversion；此工具的公式是最新年度 FCF／最新年度淨利，'
          '不是 TTM 轉換率。請保留年度口徑；缺少同期間 TTM 分子、分母與計算證據時，'
          'TTM 轉換率維持未評估，不得用相同數值替代。')


def _annual_source_paths(data):
    paths = []
    annual = {}
    for container in ('quant_metrics', 'deterministic_financial_tool_results'):
        block = data.get(container)
        calculations = block.get('calculations') if isinstance(block, dict) else None
        source = calculations.get('latest_fcf_conversion') if isinstance(calculations, dict) else None
        value = source.get('fcf_conversion_pct') if isinstance(source, dict) else None
        formula = str(source.get('formula') or '') if isinstance(source, dict) else ''
        try:
            finite = type(value) in (int, float) and math.isfinite(value)
        except OverflowError:
            finite = False
        annual[container] = (finite and ' '.join(formula.lower().split()) == 'latest annual fcf / latest annual net income')
        if annual[container]:
            paths.append(container + '.calculations.latest_fcf_conversion')
    # Saved quant_metrics is the frozen tool result; the prompt exposes the
    # same annual calculation under deterministic_financial_tool_results.
    if ('deterministic_financial_tool_results' not in data and annual['quant_metrics']):
        paths.append('deterministic_financial_tool_results.calculations.latest_fcf_conversion')
    return paths


def _split_top_level(text, separators):
    start = depth = 0
    result = []
    for index, char in enumerate(text):
        if char == '(':
            depth += 1
        elif char == ')':
            depth = max(0, depth - 1)
        elif not depth and char in separators:
            result.append((start, index, text[start:index]))
            start = index + 1
    result.append((start, len(text), text[start:]))
    return result


def _units(clean):
    heading = ''
    parents = []
    for raw_line in clean.splitlines():
        indent = len(raw_line.expandtabs(4)) - len(raw_line.expandtabs(4).lstrip())
        listed = bool(re.match(r'^\s*(?:[-+*]|\d+[.)、])\s+', raw_line))
        line = re.sub(r'[^\S\n]+|[*`]', '', raw_line)
        if not line:
            continue
        if line.startswith('#'):
            heading = line.lstrip('#')
            parents.clear()
            continue
        # Colon preambles own the following list. A listed parent only owns
        # more-indented children; sibling rows and ordinary prose end it.
        while parents and (not listed or indent < parents[-1][0]
                           or (indent == parents[-1][0] and parents[-1][1])):
            parents.pop()
        if line.endswith((':', '：')) and not _CLAIM.search(line):
            parent = re.sub(r'^(?:[-+]|\d+[.)、])', '', line)
            parents.append((indent, listed, parent))
            continue
        owner_heading = heading + ''.join(item[2] for item in parents)
        units = []
        for _, _, text in _split_top_level(line, '。；;!?！？'):
            if _SOURCE_NOTE.fullmatch(text) and units:
                units[-1] += text
            elif text:
                units.append(text)
        for text in units:
            yield owner_heading, text


def _owner_prefix(prefix):
    prefix = re.sub(r'^[-+]?\s*(?:發現|證據|觀察|結論|現金流轉化能力受限|FCF轉換率偏低)[:：]', '', prefix)
    prefix = _SOURCE_NOTE.sub('', prefix).replace(_TAG, '')
    prefix = _MEASURE.split(prefix, maxsplit=1)[0]
    prefix = re.sub(r'20\d{2}[-/]\d{1,2}(?:[-/]\d{1,2})?', '', prefix)
    prefix = _PERIOD.sub('', prefix)
    return re.sub(r'官方|個別|且|並且|同時|依據|根據|來源[:：]?|期間|口徑|至', '', prefix)


def _same_owner(data, heading, prefix, local_prefix):
    local_owner = _owner_prefix(local_prefix)
    if not _target_revenue_scope(data, local_owner, ''):
        return False
    if _target_revenue_scope(data, local_owner, '', require_explicit=True):
        return True
    if not _target_revenue_scope(data, _owner_prefix(prefix), heading):
        return False
    # A generic financial heading is neutral; an unrecognized issuer heading
    # must not borrow our annual tool just because the row omits its owner.
    neutral_heading = _PERIOD.sub('', heading)
    neutral_heading = re.sub(r'^[一二三四五六七八九十0-9]+[、.．]', '', neutral_heading)
    neutral_heading = re.sub(r'證據時點與來源|已觀測|自由現金流|FCF|現金流|轉換率|財務|品質|證據|時點|來源|分析|年度|資料|與', '', neutral_heading, flags=re.I)
    return _target_revenue_scope(data, neutral_heading, heading)


def _note_owned(data, note):
    body = re.sub(r'^\((?:來源|計算依據|source)[:：]', '', note, flags=re.I).rstrip(')')
    body = re.sub(r'(?<![A-Za-z0-9_])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+', '', body)
    return _target_revenue_scope(data, _owner_prefix(body), '')


def fcf_conversion_period_issues(text: str, data: dict | None) -> list[str]:
    """Check an explicitly cited annual result; never certify an unknown ratio."""
    if not isinstance(data, dict) or not (paths := _annual_source_paths(data)):
        return []
    clean = unicodedata.normalize('NFKC', strip_generated_audit_sections(text or '')).replace('−', '-')
    for path in paths:
        clean = re.sub(r'(?<![A-Za-z0-9_.])(?:data\.)?' + re.escape(path)
                       + r'(?:\.fcf_conversion_pct)?(?![A-Za-z0-9_.])', _TAG, clean)
    for heading, unit in _units(clean):
        claims = list(_CLAIM.finditer(unit))
        clauses = _split_top_level(unit, ',，')
        for index, claim in enumerate(claims):
            clause_index = next(i for i, (left, right, _) in enumerate(clauses)
                                if left <= claim.start() < right)
            left, right, local = clauses[clause_index]
            prefix = unit[:claim.start()]
            local_prefix = unit[left:claim.start()]
            if not _same_owner(data, heading, prefix, local_prefix):
                continue
            actual_prefix = re.split(r'但是|然而|但|實際|實績', prefix)[-1]
            actual = actual_prefix + unit[claim.start():right]
            if (not is_actual_claim(actual, len(actual_prefix), len(actual_prefix) + len(claim.group()))
                    or _ERROR.search(local) or _ERROR.search(heading)
                    or re.search(r'情境|預估|預測|假設|未來|條件|門檻', heading)
                    or re.match(r'[,，](?:此值|該值)?(?:不可採用|不採用)', unit[right:])):
                continue
            source_scope = ''
            end = claims[index + 1].start() if index + 1 < len(claims) else len(unit)
            # A citation before this claim may belong to an earlier ratio,
            # even without a comma. Only a source-only lead is shared below.
            for tag in re.finditer(re.escape(_TAG), unit[claim.end():min(right, end)]):
                tag_start = claim.end() + tag.start()
                gap = unit[claim.end():tag_start]
                notes = [note for note in _SOURCE_NOTE.finditer(unit)
                         if note.start() <= tag_start < note.end()]
                note = notes[0].group() if notes else unit[claim.end():min(right, end)]
                if not _MEASURE.search(gap) and _note_owned(data, note):
                    source_scope += note
            if clause_index and re.fullmatch(r'(?:依據|根據|來源[:：]?)?' + _TAG,
                                             clauses[clause_index - 1][2]):
                source_scope += clauses[clause_index - 1][2]
            for note in _SOURCE_NOTE.finditer(unit, claim.end(), end):
                gap = unit[claim.end():note.start()]
                if (_TAG in note.group() and not _MEASURE.search(gap) and '%' not in gap
                        and _note_owned(data, note.group())):
                    source_scope += note.group()
            for note in re.finditer(r'\([^()]*\)', unit[claim.end():right]):
                if not _SOURCE_NOTE.fullmatch(note.group()) and not _note_owned(data, note.group()):
                    source_scope = ''
                    break
            if not source_scope:
                continue
            # Only the nearest local metric period may override shared context.
            markers = list(_PERIOD.finditer(local_prefix))
            explicit_annual = bool(markers and not _TTM.fullmatch(markers[-1].group()))
            explicit_ttm = bool(markers and _TTM.fullmatch(markers[-1].group()))
            postfix = _SOURCE_NOTE.sub('', unit[claim.end():right])
            # A later, separately introduced metric cannot donate its period
            # to this value (e.g. annual ratio ... and TTM ratio ...).
            explicit_ttm = explicit_ttm or bool(re.match(
                r'^\(?(?:口徑(?:為|是)?|屬於?|採用|以|為)?(?:' + _TTM.pattern + r')',
                postfix, re.I))
            if not explicit_annual and not explicit_ttm:
                explicit_ttm = bool(_TTM.search(source_scope) or _TTM.search(heading))
                if clause_index and re.match(r'且|並且|同時|其', local_prefix):
                    previous = clauses[clause_index - 1][2]
                    explicit_ttm = explicit_ttm or bool(_TTM.search(previous) and _MEASURE.search(previous))
            if explicit_ttm:
                return [_ISSUE]
    return []
