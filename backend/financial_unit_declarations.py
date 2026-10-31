"""Reject contradictory explicit units even when historical periods are unknown."""
import re
from decimal import Decimal, InvalidOperation

_CONTRADICTION = re.compile(
 r'(?P<amount>[+-]?\d+(?:,\d{3})*(?:\.\d+)?)\s*億元\s*[（(]\s*'
 r'(?:單位|unit)\s*[:：]\s*(?:billion[_ ]twd|billion\s+TWD)\b',re.I)

def financial_unit_declaration_issues(text):
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
 return result
