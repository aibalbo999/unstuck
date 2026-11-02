"""Reject contradictory explicit units even when historical periods are unknown."""
import re
from decimal import Decimal, InvalidOperation

_CONTRADICTION = re.compile(
 r'(?P<amount>[+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*億元\s*[（(]\s*'
 r'(?:單位|unit)\s*[:：]\s*(?:billion[_ ]twd|billion\s+TWD)\b',re.I)

def financial_unit_declaration_issues(text, data=None):
 result=[]
 for number,line in enumerate(str(text or '').splitlines(),1):
  clean=re.sub(r'[*`]', '', line)
  for match in _CONTRADICTION.finditer(clean):
   # A negated correction example does not assert the bad amount.
   left=re.split(r'[。；;，,]',clean[:match.start()])[-1]
   if re.search(r'不可寫|不能寫|誤寫|錯寫|錯誤示例|錯誤範例',left):continue
   result.append({'line_number':number,'reason_code':'conflicting_explicit_money_unit',
      'text':line[:500]})
 # Explicit paired conversions must agree even if the period is unknown.
 pair = re.compile(r'(?P<base>[+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*billion[_ ]twd\s*[（(]\s*(?P<converted>[+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*億元\s*[）)]', re.I)
 for number,line in enumerate(str(text or '').splitlines(),1):
  clean=re.sub(r'[*`]', '', line)
  for match in pair.finditer(clean):
   left=re.split(r'[。；;，]',clean[:match.start()])[-1]
   if re.search(r'不可寫|不能寫|誤寫|錯寫|錯誤示例|錯誤範例',left):continue
   base=Decimal(match['base'].replace(',','')); actual=Decimal(match['converted'].replace(',','')); expected=base*10
   precision=len(match['converted'].split('.')[-1]) if '.' in match['converted'] else 0
   tolerance=Decimal(5)*(Decimal(10)**(-precision-1))
   if abs(actual-expected)>tolerance:
    result.append({'line_number':number,'reason_code':'explicit_billion_twd_to_yi_conversion_mismatch','text':line[:500]})
 result.extend(_history_series_conversion_issues(text, data))
 result.extend(_history_endpoint_conversion_issues(text, data))
 return result


def _history_endpoint_conversion_issues(text, data):
 """Reject exact vendor endpoint copies with wrong units; never verify history."""
 if not isinstance(data, dict):
  return []
 quant = data.get('quant_metrics')
 contract = quant.get('unit_contract') if isinstance(quant, dict) else None
 if not isinstance(contract, dict) or contract.get('money') != 'billion_twd':
  return []
 years, values = data.get('years'), data.get('revenue_history')
 if not isinstance(years, list) or not isinstance(values, list) or len(years) != len(values):
  return []
 try:
  source = {str(year): Decimal(str(value)) for year, value in zip(years, values)}
  if len(source) != len(years) or any(not v.is_finite() for v in source.values()):
   return []
 except (InvalidOperation, ValueError, TypeError):
  return []
 number = r'([+-]?\d+(?:,\d{3})*(?:\.\d+)?)'
 endpoint = r'(20\d{2})\s*年\s*' + number + r'\s*億(?:元|新[臺台]幣)'
 pattern = re.compile(r'供應商歷史營收從\s*' + endpoint + r'\s*成長至\s*' + endpoint)
 issues = []
 for line_number, line in enumerate(str(text or '').splitlines(), 1):
  clean = re.sub(r'[*`\s]', '', line)
  if re.search(r'同業|不可寫|不能寫|誤寫|錯寫|錯誤示例|錯誤範例', clean):
   continue
  for match in pattern.finditer(clean):
   y1, v1, y2, v2 = match.groups()
   shown = (Decimal(v1.replace(',', '')), Decimal(v2.replace(',', '')))
   expected = (source.get(y1), source.get(y2))
   if shown == expected and any(v != 0 for v in shown):
    issues.append({'line_number': line_number,
                   'reason_code': 'history_billion_twd_endpoints_mislabeled_yi',
                   'source_path': 'data.revenue_history', 'text': line[:500],
                   'period_verified': False})
 return issues


def _history_series_conversion_issues(text, data):
 """Reject copied billion values mislabeled as yi; grant no period/source proof."""
 if not isinstance(data, dict):
  return []
 quant = data.get('quant_metrics')
 contract = quant.get('unit_contract') if isinstance(quant, dict) else None
 if not isinstance(contract, dict) or contract.get('money') != 'billion_twd':
  return []
 metrics = {'營收': 'revenue_history', '淨利': 'net_income_history',
            '自由現金流': 'fcf_history', 'FCF': 'fcf_history'}
 issues = []
 amount = re.compile(r'(?P<value>[+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*億元')
 for number, line in enumerate(str(text or '').splitlines(), 1):
  clean = re.sub(r'[*`]', '', line)
  if 'history.rows' not in clean and not any(k in clean for k in metrics.values()):
   continue
  for metric, key in metrics.items():
   match = re.search(re.escape(metric) + r'[^。；;\n]{0,25}?分別為', clean, re.I)
   if not match or re.search(r'不可寫|不能寫|誤寫|錯寫|錯誤示例|錯誤範例', clean[:match.start()]):
    continue
   values = data.get(key)
   if not isinstance(values, list) or not 2 <= len(values) <= 10:
    continue
   series = re.sub(r'[（(][^（）()]*[）)]', '', clean[match.end():])
   series = re.split(r'[。；;]', series)[0]
   observed = list(amount.finditer(series))
   if len(observed) != len(values):
    continue
   try:
    raw = [Decimal(str(v)) for v in values]
    shown = [Decimal(m['value'].replace(',', '')) for m in observed]
    if not all(v.is_finite() for v in raw + shown):
     continue
    # This is a source-unit contradiction only, never a certified annual fact.
    if raw == shown and any(v != 0 for v in raw):
     issues.append({'line_number': number,
                    'reason_code': 'history_billion_twd_series_mislabeled_yi',
                    'source_path': 'data.' + key, 'text': line[:500],
                    'period_verified': False})
   except (InvalidOperation, ValueError, TypeError):
    continue
 return issues
