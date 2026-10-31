"""Exact security-code boundary for TWSE screener observations and legacy views."""
import re
POLICY='twse-exact-source-code:v1'
DAILY_URLS={'https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL','https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'}
PRICE_FIELDS=('close','latest_volume','reference_average_price','monthly_average_close','ma20','bias_pct','volume_ratio','average_volume_20d','rsi_14','macd','macd_signal','macd_histogram')
FLOW_FIELDS=('foreign_net_buy_shares','investment_trust_net_buy_shares','dealer_net_buy_shares','foreign_trust_net_buy_shares','total_net_buy_shares')

def guard_candidate(candidate):
 row=dict(candidate);metrics=dict(row.get('metrics') or {})
 ticker=str(row.get('ticker') or '');code=ticker.removesuffix('.TW') if ticker.endswith('.TW') else ''
 def bound(prefix):
  return bool(re.fullmatch('[1-9][0-9]{3}',code) and metrics.get(prefix+'_security_policy')==POLICY and metrics.get(prefix+'_security_code')==code)
 price_scope=(metrics.get('price_source')=='TWSE Free API' or 'source_security_policy' in metrics or any(str(metrics.get(k) or '').split('?')[0] in DAILY_URLS for k in ('price_source_url','volume_source_url')))
 flow_scope=metrics.get('flow_source')=='TWSE Free API' or 'flow_security_policy' in metrics
 bad_price=price_scope and not bound('source');bad_flow=flow_scope and not bound('flow')
 status='unverified' if bad_price or bad_flow else 'verified_exact_code' if price_scope or flow_scope else 'not_evaluated_non_twse'
 if bad_price or bad_flow:
  preserved=dict(row.get('unverified_security_observations') or {})
  for key in ((*PRICE_FIELDS,) if bad_price else ()) + ((*FLOW_FIELDS,) if bad_flow else ()):
   if metrics.get(key) is not None:preserved.setdefault(key,metrics[key])
   if key in metrics:metrics[key]=None
  row['unverified_security_observations']=preserved
  invalid=set()
  if bad_price:invalid.add('technical_heat')
  if bad_flow:invalid.add('institutional_accumulation')
  tags=row.get('tags')
  if isinstance(tags,list) and any(tag in invalid for tag in tags):
   preserved.setdefault('tags',list(tags))
   row['tags']=[tag for tag in tags if tag not in invalid]
  categories=row.get('categories') if isinstance(row.get('categories'),list) else [row.get('category')]
  categories=[x for x in categories if x and x not in invalid];row['categories']=categories
  if row.get('category') in invalid:row['category']=categories[0] if categories else 'unverified_source'
  if not categories:
   if row.get('reason'):preserved.setdefault('reason',row['reason'])
   row['reason']='來源證券代號待核對，相關篩選數字暫不採用。'
  warning={'code':'source_security_identity_unverified','message':'來源證券代號尚未完成核對，相關價格、成交量或法人數字暫不採用。'}
  warnings=list(row.get('source_warnings') or [])
  if warning not in warnings:warnings.append(warning)
  row['source_warnings']=warnings
 row['metrics']=metrics;row['source_security_identity_status']=status
 return row
