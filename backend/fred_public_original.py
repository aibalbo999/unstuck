"""Archive only schema-bounded public FRED observation bytes, never queries."""
import math
from datetime import date
import time


def archive_public_response(response, *, series_id, payload):
    try:
        from official_response_evidence import archive_response
        if (series_id not in {'DGS10','CPIAUCSL','VIXCLS'} or response.status_code != 200
                or getattr(response,'from_cache',False) or response.json()!=payload):
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get('observations'), list):
            return None
        allowed = {'realtime_start','realtime_end','observation_start','observation_end',
                   'units','output_type','file_type','order_by','sort_order','count','offset','limit','observations'}
        if set(payload)-allowed or len(payload['observations'])>1000:
            return None
        for key,value in payload.items():
            if key=='observations':
                continue
            if key in {'realtime_start','realtime_end','observation_start','observation_end'}:
                if not isinstance(value,str):return None
                date.fromisoformat(value)
            elif key in {'count','offset','limit','output_type'}:
                if type(value)is not int or not 0<=value<=1_000_000:return None
            elif key=='file_type':
                if value!='json':return None
            elif key=='order_by':
                if value!='observation_date':return None
            elif key=='sort_order':
                if value not in {'asc','desc'}:return None
            elif key=='units':
                if value not in {'lin','chg','ch1','pch','pc1','pca','cch','cca','log'}:return None
        for row in payload['observations']:
            if not isinstance(row,dict) or set(row)-{'realtime_start','realtime_end','date','value'}:
                return None
            if not {'date','value'}<=set(row):return None
            for key,value in row.items():
                if not isinstance(value,str)or len(value)>64:return None
                if key!='value':date.fromisoformat(value)
                elif value!='.' and not math.isfinite(float(value)):return None
        receipt=archive_response(response.content,
            source_url='https://api.stlouisfed.org/fred/series/observations?series_id='+series_id,
            retrieved_at=time.time(),evidence_kind='decoded_complete_http_response_body',max_bytes=2_000_000)
        if receipt.get('status')!='archived':return None
        receipt.update(http_status_observed=True,response_complete=True,cache_hit=False)
        return receipt
    except Exception:
        return None
