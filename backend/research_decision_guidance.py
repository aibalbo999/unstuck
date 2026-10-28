"""Source-bound arithmetic aid, without assigning a decision or time horizon."""
from __future__ import annotations

import json
import math


def _positive(value):
    try:
        return (not isinstance(value, bool) and isinstance(value, (int, float))
                and math.isfinite(value) and value > 0)
    except OverflowError:
        return False


def decision_arithmetic_prompt(context):
    data = context.get('data') or {}
    current = data.get('current_price')
    outputs = context.get('structured_outputs') or {}
    valuation = outputs.get(4, outputs.get('4')) or {}
    targets = valuation.get('price_targets') if isinstance(valuation, dict) else None
    if not _positive(current) or not isinstance(targets, dict):
        return ''
    rows = [{'field': 'structured_outputs.4.price_targets.' + name, 'price': price,
             'relative_return_pct': round((price / current - 1) * 100, 4)}
            for name, price in targets.items() if _positive(price)]
    if not rows:
        return ''
    return '\n'.join((
        '【同一輸入的報酬算術核對】',
        json.dumps({'current_price': current, 'current_price_field': 'data.current_price',
                    'valuation_scenarios': rows}, ensure_ascii=False, allow_nan=False),
        '這是既有情境相對現價的算術，不認定情境期間，也不代選推薦。'
        '只有證據支持其為同一期限目標，才能移入 3／6／12 個月欄位。'
        '輸出前按實際 12 個月目標核對推薦與報酬契約；持有不能代稱等待。'
        '不合時重新評估證據、分類與目標，不可為過關任意改價或改標籤；缺證據如實保留未評估。',
    ))
