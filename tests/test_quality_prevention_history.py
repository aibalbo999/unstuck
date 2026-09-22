"""15 retained historical cases: 12 September22 jobs, two earlier canaries, 2305."""
import json
import copy
from pathlib import Path
import pytest
from institutional_evidence import institutional_evidence_issues, institutional_evidence_diagnostics
from institutional_evidence_prompt import build_institutional_source_prompt

DIR=Path(__file__).parent/'fixtures'
PASS={'2883.TW','2618.TW','2033.TW','6715.TW','4958.TW','2610.TW'}
VERIFIED_SCOPE_FIXES={'cefda8b5272240089b1881fe181c90bf', 'afa91c6762974ca6b5addadfdf293fac'}
CASES=[(row['job_id'],row['analysis'],{'ticker':row['ticker'],'institutional_trading':row['institutional_data']},
        row['ticker'] not in PASS and row['job_id'] not in VERIFIED_SCOPE_FIXES)
       for row in json.loads((DIR/'institutional_20260922_blocked.json').read_text())]
for name in ['institutional_3324_canary','institutional_2033_round2']:
    row=json.loads((DIR/(name+'.json')).read_text())
    CASES.append((name,row['original_responses'][-1],row['data'],False))
row=json.loads((DIR/'institutional_2305_20260922.json').read_text())
CASES.append(('88af5ff6cda245ce9a6089b600274020',row['candidates'][-1]['raw'],row['data'],True))

@pytest.mark.parametrize('identity,text,data,blocked',CASES,ids=[c[0] for c in CASES])
def test_historical_gate_classification_and_explicit_source_facts(identity,text,data,blocked):
    issues=institutional_evidence_issues(text,data)
    assert bool(issues)==blocked
    diagnostics=institutional_evidence_diagnostics(text,data)
    assert bool(diagnostics)==blocked
    for item in diagnostics:
        assert text[slice(*item['span'])]==item['claim']
    facts=build_institutional_source_prompt(data)
    assert '沒有可逐項核驗' not in facts
    assert institutional_evidence_issues(facts,data)==[]


@pytest.mark.parametrize('identity,text,data,blocked', [c for c in CASES if c[0] in VERIFIED_SCOPE_FIXES])
def test_fixed_historical_scope_still_requires_original_population_value(identity,text,data,blocked):
    changed = copy.deepcopy(data)
    for unit in ('shares', 'thousand_shares'):
        changed['institutional_trading'][f'net_buy_{unit}_by_category']['dealer'] = 99999999
    assert institutional_evidence_issues(text, changed)
