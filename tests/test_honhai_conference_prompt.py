from copy import deepcopy
import json,hashlib
import pytest
from test_honhai_conference import harness
from data_fetch.market_sources import honhai_conference as hh
from conference_presentation_prompt import presentation_prompt_context,without_presentation_documents
from prompt_evidence import prompt_evidence_copy

@pytest.mark.parametrize('role',[3,5,12])
def test_declared_transcript_roles_receive_bounded_visible_quotes_without_date_or_accuracy_inference(harness,role):
    value=hh._fetch()['context'];before=deepcopy(value);view=presentation_prompt_context(value,role);doc=view['documents'][0]
    assert view['transcript_available']is True and doc['document_kind']=='transcript'
    assert doc['event_date_basis']=='official_transcript_cover_declared_date_time' and doc['event_time_Taipei']=='15:00'
    assert doc['source_page_displayed_date']=='2026-07-29' and doc['published_at']is doc['material_file_date']is None
    assert doc['transcript_accuracy_independently_verified']is False and doc['coverage_status']=='partial'
    assert sum(len(p['text'])for p in doc['pages'])<=2500 and len(doc['pages'])<=6
    assert 'raw_response_path'not in json.dumps(view) and value==before
    original={p['page_number']:p['text']for p in value['documents'][0]['pages']}
    assert all(original[p['page_number']].startswith(p['text'])and hashlib.sha256(p['text'].encode()).hexdigest()==p['prompt_excerpt_sha256']for p in doc['pages'])

def test_base_roles_do_not_get_full_transcript_or_internal_archive_metadata(harness):
    v=hh._fetch()['context'];before=deepcopy(v)
    stripped=without_presentation_documents(v);view=prompt_evidence_copy({'earnings_call':stripped})
    assert 'documents'not in view['earnings_call'] and 'raw_response_path'not in json.dumps(view) and 'honhai_conference_receipt'not in json.dumps(view)
    assert v==before and presentation_prompt_context(v,7)=={}

def test_legacy_or_other_transcripts_keep_existing_base_behavior():
    v={'documents':[{'document_kind':'transcript','source':'legacy','pages':[{'page_number':1,'text':'original'}]}]}
    assert without_presentation_documents(v)==v
