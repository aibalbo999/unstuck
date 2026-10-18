"""Exact published ChipMOS original; private-child public behavior."""
from pathlib import Path
import importlib,json
import pytest
RAW=(Path(__file__).parent/'fixtures/source_acquisition/chipmos_2026q2_transcript.pdf').read_bytes()
DIGEST='712d554e7f3878cbcb7705bdfc7f9977f410661e176af6288f74fc3e81371d7a'

def extract(raw=RAW,**kwargs):
 try:module=importlib.import_module('chipmos_transcript_pdf_reader')
 except ModuleNotFoundError as exc:
  if exc.name!='chipmos_transcript_pdf_reader':raise
  from source_pdf_reader import extract_pdf_pages
  return extract_pdf_pages(raw,**kwargs)
 return module.extract_chipmos_transcript_pages(raw,**kwargs)

def test_complete_original_returns_exact_eight_pages_and_cursor_evidence():
 value=extract(timeout_seconds=10)
 assert value['page_count']==8 and value['empty_pages']==value['garbled_pages']==[]
 assert value['coverage_status']=='complete' and value['content_sha256']==DIGEST
 proof=value['xref_validation_evidence']
 assert proof['complete_original_sha256']==DIGEST and proof['in_use_objects']==68
 assert proof['cursor_delta_bytes']==1 and proof['raw_bytes_rewritten'] is False
 assert 'MATERIAL ERRORS, OMISSIONS, OR INACCURACIES' in value['pages'][7]['text']

def test_generic_worker_retains_warning_rejection():
 from source_pdf_reader import extract_pdf_pages,SourcePdfError
 with pytest.raises(SourcePdfError)as error:extract_pdf_pages(RAW,timeout_seconds=10)
 assert error.value.reason=='parser_warning'

@pytest.mark.parametrize('raw',[None,False,b'',bytearray(b'%PDF-1.7'),b'x'*(8*1024*1024+1)])
def test_invalid_input_does_not_start_worker(monkeypatch,raw):
 import chipmos_transcript_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid input started worker'))
 with pytest.raises(SourcePdfError)as error:extract(raw)
 assert error.value.reason=='invalid_input'

@pytest.mark.parametrize('seconds',[True,False,0,-1,11,float('nan'),float('inf'),'10'])
def test_invalid_timeout_does_not_start_worker(monkeypatch,seconds):
 import chipmos_transcript_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 monkeypatch.setattr(module,'_run_worker',lambda *a,**k:pytest.fail('invalid timeout started worker'))
 with pytest.raises(SourcePdfError)as error:extract(timeout_seconds=seconds)
 assert error.value.reason=='invalid_timeout'

@pytest.mark.parametrize('case',['points_other_object','points_inside_header','non_lf_prefix','extra_header_whitespace','duplicate_object_id','bad_xref_entry','extra_trailer'])
def test_complete_xref_structure_rejects_other_repairs(case):
 import time
 from chipmos_transcript_pdf_reader import _qualify_xref
 raw=RAW;entry=678966+len(b'xref\n0 69\r\n')+20
 if case=='points_other_object':raw=raw[:entry]+b'0000678540'+raw[entry+10:]
 elif case=='points_inside_header':raw=raw[:entry]+b'0000678650'+raw[entry+10:]
 elif case=='non_lf_prefix':raw=raw[:678648]+b' '+raw[678649:]
 elif case=='extra_header_whitespace':raw=raw[:678648]+raw[678648:].replace(b'\n1 0 obj\n',b'\n1  0 obj\n',1)
 elif case=='duplicate_object_id':raw=raw[:678648]+raw[678648:].replace(b'\n1 0 obj\n',b'\n2 0 obj\n',1)
 elif case=='bad_xref_entry':raw=raw[:entry+17]+b'f'+raw[entry+18:]
 else:raw+=b'\ntrailer\n<<>>\n'
 with pytest.raises(ValueError):_qualify_xref(raw,time.monotonic()+10)
 from source_pdf_reader import SourcePdfError
 with pytest.raises(SourcePdfError)as error:extract(raw)
 assert error.value.reason=='invalid_pdf'

def test_every_native_page_matches_independent_original_text():
 from hashlib import sha256
 expected=['60bb2f4668ead6cb086171dea11651ccbf77598d3295deee18e80b1f7366a2f4','a08107847c1e2c4d4e0e27d0759e605ddd1eba75ee76ca872b47991178158479','2c39b84e4c4d042875920b2503c60c4b45aa6573b9370c263d3ba2628edd63d4','a3b1288e1f137be3dea5c22fabd9e973bb55f0d71c5deeaa4ed375086b65e7dd','3fc2b7c44ad48d9ee82883a189d40bb0ea322f36a7599c59952549fac53302c6','dfef0eec3870b64cfca14e7b72649162e33ec645510bf7649ae0529d4b37eaa5','4b5418e39d4c4fd833c551b1ef3b9380b6993c5bc36f02e362802b1a6e3163ab','14e954682dc4f6b546829353f76518b7fb49d6e10583f7982fae946a101199c5']
 result=extract()
 assert [sha256(p['text'].encode()).hexdigest()for p in result['pages']]==expected
 assert sha256(RAW).hexdigest()==DIGEST

def test_unrelated_warning_stays_fatal_through_public_private_worker(monkeypatch,tmp_path):
 import chipmos_transcript_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 worker=tmp_path/'warning_worker.py'
 backend=str(Path(module.__file__).resolve().parent)
 worker.write_text('import sys,logging\nsys.path.insert(0,'+repr(backend)+')\nimport pypdf\nimport source_pdf_worker as common\nimport chipmos_transcript_pdf_worker as specific\noriginal=pypdf.PdfReader.read_object_header\ndef noisy(self,stream):\n logging.getLogger("pypdf").warning("independent unexpected stream diagnostic")\n return original(self,stream)\npypdf.PdfReader.read_object_header=noisy\ncommon._extract=specific._extract\ncommon.main()\n')
 run=module._run_worker
 def special(raw,deadline,*,worker_command):
  command=list(worker_command);command[2]=str(worker)
  return run(raw,deadline,worker_command=command)
 monkeypatch.setattr(module,'_run_worker',special)
 with pytest.raises(SourcePdfError)as error:extract()
 assert error.value.reason=='parser_warning'

@pytest.mark.parametrize('change',['missing','digest','bool_integer','offset','cursor'])
def test_parent_rejects_altered_worker_xref_evidence(monkeypatch,change):
 import chipmos_transcript_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 value=extract();proof=value['xref_validation_evidence']
 if change=='missing':value.pop('xref_validation_evidence')
 elif change=='digest':proof['complete_original_sha256']='0'*64
 elif change=='bool_integer':proof['raw_bytes_rewritten']=0
 elif change=='offset':proof['classic_xref_offset']+=1
 else:proof['cursor_delta_bytes']=2
 monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(value).encode())
 with pytest.raises(SourcePdfError)as error:extract()
 assert error.value.reason=='invalid_worker_result'

def test_parent_deadline_checked_after_final_xref_evidence(monkeypatch):
 import chipmos_transcript_pdf_reader as module
 from source_pdf_reader import SourcePdfError
 value=extract();clock=[0.]
 monkeypatch.setattr(module.time,'monotonic',lambda:clock[0])
 monkeypatch.setattr(module,'_run_worker',lambda *a,**k:json.dumps(value).encode())
 qualifier=module._qualify_xref
 def slow(*args):
  result=qualifier(*args);clock[0]=10.;return result
 monkeypatch.setattr(module,'_qualify_xref',slow)
 with pytest.raises(SourcePdfError)as error:extract(timeout_seconds=10)
 assert error.value.reason=='timeout'
