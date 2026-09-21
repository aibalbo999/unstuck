"""TPEx OpenAPI margin balances; field contract verified against its official schema."""
from datetime import date
import re

URL = 'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance'
SOURCE = 'TPEx OpenAPI tpex_mainboard_margin_balance'
# Official OpenAPI field identities; volume unit corroborated by TPEx EDIS S23.
_FIELDS = {'margin_previous_balance':'MarginPurchaseBalancePreviousDay',
           'margin_purchase':'MarginPurchase','margin_sale':'MarginSales',
           'margin_cash_repayment':'CashRedemption','margin_balance':'MarginPurchaseBalance',
           'short_previous_balance':'ShortSaleBalancePreviousDay','short_sale':'ShortSale',
           'short_purchase':'ShortConvering','short_cash_repayment':'StockRedemption',
           'short_balance':'ShortSaleBalance','offset':'Offsetting'}


def _date(value):
    text = str(value or '')
    try:
        if re.fullmatch(r'\d{7}',text):
            return date(int(text[:3])+1911,int(text[3:5]),int(text[5:])).isoformat()
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def fetch_tpex_margin(code, *, http_get, parse_int, session=None, timeout=20):
    base = {'ticker':code,'source':SOURCE,'source_url':URL,'market':'TPEX'}
    try:
        rows = http_get(URL,session=session,timeout=timeout,provider=SOURCE).json()
        matches = [row for row in rows if isinstance(row,dict) and str(row.get('SecuritiesCompanyCode')).strip()==code] if isinstance(rows,list) else []
        if len(matches)!=1:
            return {**base,'status':'unavailable','reason_code':'record_not_found' if not matches else 'ambiguous_records',
                    'message':'上櫃來源未提供唯一可用的標的紀錄；不推定為零。'}
        row=matches[0];observed=_date(row.get('Date'))
        quantities={field:parse_int(row.get(raw_field)) for field,raw_field in _FIELDS.items()}
        if not any(value is not None for value in quantities.values()):
            return {**base,'status':'unavailable','reason_code':'quantities_unavailable',
                    'as_of_date':observed,'message':'上櫃來源有標的紀錄，但未提供可用融資券數值。'}
        return {**base,'status':'success','company_name':str(row.get('CompanyName') or ''),
                'as_of_date':observed,'margin_as_of_date':observed,'margin_date_status':'reported' if observed else 'unknown',
                'margin_unit':'thousand_shares','unit_basis':'TPEx EDIS S23 margin field units',
                **quantities,
                'borrowed_short_status':'unavailable','borrowed_short_reason_code':'not_in_margin_endpoint'}
    except Exception:
        return {**base,'status':'unavailable','reason_code':'fetch_failed','message':'上櫃融資券來源連線或格式失敗。'}
