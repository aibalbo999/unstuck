"""Exact public original may recover only its recorded xref LF boundary defect."""
from pathlib import Path
from hashlib import sha256
import json,re
import pytest
from source_pdf_reader import extract_pdf_pages,SourcePdfError
from test_source_pdf_reader import make_pdf
R=Path(__file__).resolve().parents[1]
D=R/'docs/evidence/source-acquisition/20261015/voltronic-parser-review'
PDF=R/'docs/evidence/source-acquisition/20261014/free-entrance-next/conference/native-6409-english.body'

def test_original_pdf_extracts_with_bound_header_recovery_evidence():
 raw=PDF.read_bytes()
 v=extract_pdf_pages(raw)
 expected=json.loads((D/'diagnostic.json').read_text())['pages']
 assert v['pages']==expected and v['page_count']==32
 proof=v['object_header_whitespace_evidence']
 assert proof['content_sha256']==sha256(raw).hexdigest() and proof['warning_count']==217
 assert proof['policy']=='exact-original-xref-leading-LF-v1'

@pytest.mark.parametrize('edit',['body','eof'])
def test_unqualified_revision_retains_warning_rejection(edit):
 raw=PDF.read_bytes()
 raw=raw.replace(b'11:09:47',b'11:09:48',1)if edit=='body'else raw+b'\n'
 if edit=='body' and raw==PDF.read_bytes():raw=raw.replace(b'/Catalog',b'/Catalog ',1)
 with pytest.raises(SourcePdfError):extract_pdf_pages(raw)

def test_other_pdf_with_same_one_byte_xref_error_is_not_silently_repaired():
 raw=make_pdf([b'Original text'])
 raw=re.sub(rb'([0-9]{10}) 00000 n ',lambda m:f'{int(m[1])-1:010} 00000 n '.encode(),raw)
 with pytest.raises(SourcePdfError):extract_pdf_pages(raw)

def test_healthy_original_has_no_recovery_evidence():
 v=extract_pdf_pages(make_pdf([b'Original text']))
 assert v['pages'][0]['text']=='Original text'and 'object_header_whitespace_evidence'not in v

@pytest.mark.parametrize('edit',['missing','boolean','count','digest','policy'])
def test_parent_rejects_forged_or_missing_recovery_proof(edit):
 import source_pdf_reader as reader
 v=extract_pdf_pages(PDF.read_bytes())
 p=v['object_header_whitespace_evidence']
 if edit=='missing':v.pop('object_header_whitespace_evidence')
 elif edit=='boolean':p['raw_bytes_modified']=0
 elif edit=='count':p['warning_count']-=1
 elif edit=='digest':p['observations_sha256']='0'*64
 else:p['policy']='ignore_all_warnings'
 with pytest.raises(SourcePdfError,match='invalid_worker_result'):
  reader._validate_result(v,sha256(PDF.read_bytes()).hexdigest())


def test_other_known_whitespace_original_remains_rejected():
 raw=(R/'docs/evidence/source-acquisition/20261015/mega-free-conference/presentation.body').read_bytes()
 with pytest.raises(SourcePdfError):extract_pdf_pages(raw)

@pytest.mark.parametrize('kind',['unknown_warning','different_logger','outside_header','duplicate','incomplete'])
def test_whitelisted_original_does_not_accept_other_diagnostics(kind):
 import io,logging
 from source_pdf_header_whitespace import HeaderWhitespaceQualification
 q=HeaderWhitespaceQualification(PDF.read_bytes())
 offset,number,generation=json.loads((D/'qualified-header-observations.json').read_text())[0]
 stream=io.BytesIO(q.raw);stream.seek(offset)
 msg=f'Superfluous whitespace found in object header {str(number).encode()!r} {str(generation).encode()!r}'
 record=logging.LogRecord('pypdf._reader',30,'',0,msg,(),None)
 if kind=='unknown_warning':record.msg='Broken object reference'
 if kind=='different_logger':record.name='pypdf.generic'
 if kind=='outside_header':assert not q.accepts(record)
 elif kind=='incomplete':
  with pytest.raises(ValueError):q.evidence()
 else:
  with q.header(stream):
   if kind=='duplicate':assert q.accepts(record)
   assert not q.accepts(record)
