"""Exact legacy comparison: speed up path work without changing evidence admission."""
import gzip,json,copy,random
from pathlib import Path
import pytest
import evidence_exit_gate as gate
from evidence_claim_boundaries import with_match_normalization_cache

FIXTURES=Path(__file__).parent/'fixtures'
namespace=dict(vars(gate));exec((FIXTURES/'evidence_flatten_preoptimization.py.txt').read_text(),namespace)
legacy=namespace['flatten_snapshot_numbers']
CASES=json.loads(gzip.decompress((FIXTURES/'quality_oct14_saved.json.gz').read_bytes()))

@with_match_normalization_cache
def compare(snapshot):
    before=copy.deepcopy(snapshot)
    expected=legacy(snapshot,eligible_only=True)
    actual=gate.flatten_snapshot_numbers(snapshot,eligible_only=True)
    assert actual==expected and snapshot==before
    # Public complete flatten retains its full legacy semantics too.
    assert gate.flatten_snapshot_numbers(snapshot)==legacy(snapshot)

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['ticker'])
def test_actual_sixteen_saved_reports_identical(case):compare(case['snapshot'])


def test_complex_keys_boundaries_dates_and_unicode_do_not_bypass_exclusions():
    snapshot={'data':{'year':2026,'Year':123,'dates':[1,2],
       'a.timestamp.amount':10,'generated_at':[2,3],'checked_at_extra':8,
       '技術':{'日均值':12},'as_of.extra':5,'x':{'confidence':{'score':3}},
       'foo[0].date':3,'source_record_archive':{'nested':[1,2]},
       'price_history':{'dates':['2026-10-01','2026-10-02'],'prices':[3,4]}},
       'oos_evaluation_inputs':{'data':{'financial':{'amount':123}}}}
    compare(snapshot)


def test_generated_nested_key_paths_match_without_evidence_cache():
    random.seed(42)
    keys=['price','data','timestamp','TimeStamp','year','years','a.b','a[0]','_confidence','confidence','as_of','股數','source','archive','foo-bar']
    def build(depth):
        if depth==0:return random.choice([None,True,1,3.25,'12.5 TWD'])
        return {random.choice(keys):[build(depth-1),build(depth-1)] for _ in range(3)}
    for _ in range(20):compare(build(3))
