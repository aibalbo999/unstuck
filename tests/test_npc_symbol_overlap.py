"""A visible square cannot substantiate multiple font mapping claims."""
from pathlib import Path
from copy import deepcopy
import json
import pytest
from source_pdf_symbols import valid_symbol_evidence,POLICY,PROGRAM_SHA256,CMAP_SHA256
D=Path(__file__).resolve().parents[1]/'docs/evidence/source-acquisition/20261015/npc-pcb-conference-integration'
@pytest.mark.parametrize('visible,expected',[(1,False),(2,True)])
def test_mixed_legacy_and_new_font_claims_share_one_visible_budget(visible,expected):
 new=deepcopy(json.loads((D/'1303-normalized-native.json').read_text())['symbol_mapping_evidence'][0])
 new.update(page_number=1,occurrences=1)
 old=dict(policy=POLICY,page_number=1,font_program_sha256=PROGRAM_SHA256,cmap_sha256=CMAP_SHA256,source_font='Wingdings2',source_character='U+F0A1',replacement_character='U+25A0',occurrences=1)
 evidence=sorted([old,new],key=lambda r:(r['page_number'],r['policy'],r['source_character']))
 assert valid_symbol_evidence(evidence,[{'page_number':1,'text':'■'*visible}])is expected
