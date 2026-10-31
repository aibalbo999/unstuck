import pytest
from test_finmind_monthly_lineage import native,acquire,ROWS

@pytest.mark.parametrize('created',['','2026-04-21','2026-10-11'])
def test_documented_ingestion_date_retains_full_body_binding(native,created):
 loader,events,state=native;state['rows'][0]['create_time']=created
 r=acquire(loader);proof=r['audit'].get('sdk_payload_lineage')
 assert proof, 'Documented create_time schema loses monthly body lineage'
 assert proof['historical_pit_verified'] is False and proof['independent_primary_source_verified'] is False
 assert r['value']==['2026年9月: NT$1.23億']
@pytest.mark.parametrize('created',[None,1,True,'2026-02-30','2026-04-20','2026-11-01','2026-10-11T00:00:00','secret-query'])
def test_bad_ingestion_date_does_not_upgrade_evidence(native,created):
 loader,events,state=native;state['rows'][0]['create_time']=created
 r=acquire(loader);assert r['value'] and 'sdk_payload_lineage' not in r['audit']
def test_ingestion_date_is_not_official_publication_or_historical_query_end(native):
 from finmind_monthly_lineage import _rows
 from datetime import date
 row={**ROWS[0],'date':'2025-10-10','revenue_year':2025,'create_time':'2026-04-21'}
 assert _rows([row],'2330.TW',date(2025,1,1),date(2025,12,31))
