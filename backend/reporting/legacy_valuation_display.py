"""Narrow view-only correction of non-positive historical scenario prices."""
import re

_SCENARIO_ZERO = re.compile(r'(?P<label>熊市情境|基本情境(?:估值)?|牛市情境)(?P<gap>(?:[^<]|<[^>]+>){0,120}?)(?:NT\$|NT&#36;)\s*0(?:\.0+)?(?![\d.])')

def repair_legacy_valuation_display(text):
    # Label-bound: legitimate zero cash flow/EPS/holdings are not missing prices.
    repaired = _SCENARIO_ZERO.sub(lambda m: m['label'] + m['gap'] + 'N/A（原估值輸出不可用）', str(text or ''))
    if repaired != str(text or ''):
        repaired = re.sub(r'(<div class="price-target-card"[^>]*>.*?N/A（原估值輸出不可用）.*?<div class="pt-pct"[^>]*>)[^<]*', r'\1N/A', repaired, flags=re.S)
        repaired = repaired.replace('估值仍落在三情境可解釋區間', '估值不可用，未進行三情境範圍比較')
    return repaired
