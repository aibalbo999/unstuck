"""FinMind individual-income/YTD-cash-flow vendor contract; synthetic only."""
import pytest
from external_data_twse import _build_payload

DATES=('2025-06-30','2025-09-30','2025-12-31','2026-03-31')
def row(day,kind,value):return {'date':day,'stock_id':'1623','type':kind,'value':value,'origin_name':kind}
def inputs():
 income=[row(d,k,v)for d in DATES for k,v in [('Revenue',100.),('GrossProfit',40.),('OperatingIncome',20.),('IncomeAfterTaxes',10.)]]
 cash=[row(d,k,v)for d,ocf,capex in [('2025-03-31',10.,-3.),('2025-06-30',25.,-8.),('2025-09-30',40.,-13.),('2025-12-31',60.,-20.),('2026-03-31',15.,-4.)]for k,v in [('NetCashInflowFromOperatingActivities',ocf),('PurchaseOfPropertyPlantAndEquipment',capex)]]
 return income,cash

def test_ytd_cashflow_uses_matching_prior_year_bridge_not_four_quarter_sum():
 income,cash=inputs();p=_build_payload(income,[],cash,'FinMind_TWSE')
 assert p['revenue_ttm_raw']==400.
 assert p['free_cash_flow_raw']==44.  # (60-10+15)+(-20-(-3)+(-4))

def test_full_year_cashflow_is_december_ytd_only():
 income,cash=inputs();income=[row(d,'Revenue',100.)for d in ('2025-03-31',*DATES[:3])]
 p=_build_payload(income,[],cash,'FinMind_TWSE')
 assert p['free_cash_flow_raw']==40.  # 60+(-20), not sum of YTD rows

def test_missing_prior_ytd_does_not_guess_cashflow():
 income,cash=inputs();cash=[r for r in cash if r['date']!='2025-03-31']
 assert _build_payload(income,[],cash,'FinMind_TWSE')['free_cash_flow_raw']is None

def test_missing_income_quarter_never_labels_partial_sum_ttm():
 income,cash=inputs();income=[r for r in income if r['date']!='2025-09-30']
 p=_build_payload(income,[],cash,'FinMind_TWSE')
 assert p is None or all(p[k]is None for k in ('revenue_ttm_raw','net_income_ttm_raw','gross_margin_raw','operating_margin_raw','profit_margin_raw','free_cash_flow_raw'))

def test_partial_metric_does_not_borrow_other_quarter_coverage():
 income,cash=inputs();income=[r for r in income if not(r['date']=='2025-09-30'and r['type']=='Revenue')]
 p=_build_payload(income,[],cash,'FinMind_TWSE')
 assert p['revenue_ttm_raw']is None and p['gross_margin_raw']is None
 assert p['net_income_ttm_raw']==40.

def test_conflicting_same_date_metric_keeps_ttm_unknown():
 income,cash=inputs();income.append(row('2025-09-30','Revenue',999.))
 p=_build_payload(income,[],cash,'FinMind_TWSE')
 assert p['revenue_ttm_raw']is None and p['gross_margin_raw']is None

def test_vendor_cumulative_operating_cashflow_exact_type_supported():
 income,cash=inputs()
 for r in cash:
  if r['type']=='NetCashInflowFromOperatingActivities':r['type']='CashFlowsFromOperatingActivities'
 assert _build_payload(income,[],cash,'FinMind_TWSE')['free_cash_flow_raw']==44.

def test_generic_ppe_cannot_supply_missing_explicit_capex():
 income,cash=inputs()
 for r in cash:
  if r['type']=='PurchaseOfPropertyPlantAndEquipment':r['type']='PropertyAndPlantAndEquipment'
 assert _build_payload(income,[],cash,'FinMind_TWSE')['free_cash_flow_raw']is None

def test_non_finmind_payload_uses_its_original_contract():
 income,cash=inputs()
 assert _build_payload(income,[],cash,'TWSE_OpenAPI')['free_cash_flow_raw']==95.


def test_future_quarter_is_not_admitted_as_current_ttm(monkeypatch):
 import external_data_twse as x
 monkeypatch.setattr(x,'_today_iso',lambda:'2026-01-15')
 income,cash=inputs();p=x._build_payload(income,[],cash,'FinMind_TWSE')
 assert p is None

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-float('inf'),1e31,1e-21])
def test_nonfinite_or_outside_native_numeric_domain_metric_remains_unknown(bad):
 income,cash=inputs()
 for r in income:
  if r['type']=='Revenue':r['value']=bad
 p=_build_payload(income,[],cash,'FinMind_TWSE')
 assert p['revenue_ttm_raw']is None and p['profit_margin_raw']is None

def test_missing_explicit_cashflow_date_cannot_borrow_income_date():
 income,cash=inputs();cash=[r for r in cash if r['date']!='2026-03-31']
 assert _build_payload(income,[],cash,'FinMind_TWSE')['free_cash_flow_raw']is None


def test_conflicting_cashflow_aliases_do_not_select_first_value():
 income,cash=inputs();cash.append(row('2026-03-31','CashFlowsFromOperatingActivities',999.))
 assert _build_payload(income,[],cash,'FinMind_TWSE')['free_cash_flow_raw']is None

def test_four_arbitrary_dates_do_not_make_four_calendar_quarters():
 income,cash=inputs()
 for r in income:
  if r['date']=='2025-09-30':r['date']='2025-09-29'
 assert _build_payload(income,[],cash,'FinMind_TWSE')is None
