from copy import deepcopy
from evidence_exit_gate import evaluate_report_evidence

DATA={'ticker':'1623.TW','company_name':'大東電','financial_currency':'TWD','years':['2024','2025'],'net_income_history':[.733007,.816874],'revenue_history':[5.482989,6.60704]}

def claims(text):
 return [x for x in evaluate_report_evidence(text,{'data':deepcopy(DATA)})['sampled_claims']if x.get('financial_metric')=='淨利']

def test_anaphoric_profit_comparison_cannot_borrow_latest_revenue_year():
 text='官方個別財報年度營收自2024年度之54.82989億元增至2025年度之66.0704億元，淨利亦自7.33007億元增至8.16874億元。'
 rows=claims(text)
 assert rows and rows[0]['status']=='unverifiable',rows
 assert rows[0]['verification_reason_code']=='financial_amount_scope_unbound'
 assert rows[0]['raw_text']==text and rows[0]['reported_value']==7.33007

def test_explicit_wrong_annual_profit_remains_mismatch():
 rows=claims('大東電2025年度淨利為7.33007億元。')
 assert len(rows)==1 and rows[0]['status']=='mismatch',rows

def test_separate_explicit_years_do_not_become_ambiguous():
 rows=claims('大東電2024年度淨利為7.33007億元，2025年度淨利為8.16874億元。')
 assert len(rows)==2 and all(x['status']=='verified'for x in rows),rows
