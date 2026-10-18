"""Three fixed full China Airlines books; private bounded native page extraction."""
from hashlib import sha256
from pathlib import Path
import json,math,sys,time
from source_pdf_reader import _run_worker,SourcePdfError,PARSER_VERSION,TIMEOUT_LIMIT
SELECTED=(1,3,6,11,12,13)
PAGE_COUNTS={2022:90,2024:94,2025:91}
INPUT_LIMIT=3_000_000
CHAR_LIMIT=100_000
def extract_cal_book(raw,year,*,timeout_seconds=10):
    if type(year)is not int or year not in PAGE_COUNTS:raise SourcePdfError('unsupported_annual_profile')
    if (not isinstance(raw,bytes)or not raw.startswith(b'%PDF-')or not 0<len(raw)<=INPUT_LIMIT
            or type(timeout_seconds)not in(int,float)or not math.isfinite(timeout_seconds)
            or not 0<timeout_seconds<=TIMEOUT_LIMIT):raise SourcePdfError('invalid_input')
    digest=sha256(raw).hexdigest();deadline=time.monotonic()+timeout_seconds
    command=[sys.executable,'-B',str(Path(__file__).with_name('cal_annual_pdf_worker.py')),str(deadline),str(year)]
    try:
        result=json.loads(_run_worker(raw,deadline,worker_command=command))
        if time.monotonic()>=deadline:raise SourcePdfError('timeout')
        if isinstance(result,dict)and set(result)=={'error'}:
            known={'invalid_pdf','encrypted_pdf','page_limit','character_limit','empty_or_garbled_selected_document',
                   'parser_unavailable','parser_version_mismatch','parser_warning','stream_limit','resource_limits_unavailable',
                   'timeout','invalid_input','memory_limit','segment_limit','unsupported_text_position','invalid_text_position'}
            reason=result['error']
            raise SourcePdfError(reason if isinstance(reason,str)and reason in known else'worker_failed')
        keys={'page_count','selected_full_physical_pages','extraction_mode','pages','empty_pages','garbled_pages','coverage_status','parser_version','content_sha256'}
        if (not isinstance(result,dict)or set(result)!=keys or type(result['page_count'])is not int or result['page_count']!=PAGE_COUNTS[year]
                or result['selected_full_physical_pages']!=list(SELECTED)or any(type(n)is not int for n in result['selected_full_physical_pages'])
                or result['extraction_mode']!='native_show_operation_coordinates'or result['parser_version']!=PARSER_VERSION
                or result['content_sha256']!=digest or result['empty_pages']!=[]or result['garbled_pages']!=[]
                or result['coverage_status']!='selected_native_text_complete'or not isinstance(result['pages'],list)or len(result['pages'])!=len(SELECTED)):
            raise SourcePdfError('invalid_worker_result')
        count=0
        for number,page in zip(SELECTED,result['pages']):
            if (not isinstance(page,dict)or set(page)!={'page_number','text','segments','width','height','rotation'}
                    or type(page['page_number'])is not int or page['page_number']!=number or not isinstance(page['text'],str)or not page['text'].strip()
                    or type(page['rotation'])is not int or page['rotation']!=0 or not isinstance(page['segments'],list)or not 1<=len(page['segments'])<=10000
                    or any(type(page[k])not in(int,float)or not math.isfinite(page[k])or not 0<page[k]<=1000 for k in ('width','height'))):
                raise SourcePdfError('invalid_worker_result')
            count+=len(page['text'])
            for s in page['segments']:
                if (not isinstance(s,dict)or set(s)!={'text','x','end_x','y','font_height'}or not isinstance(s['text'],str)or len(s['text'])>10000
                        or any(type(s[k])not in(int,float)or not math.isfinite(s[k])for k in ('x','end_x','y','font_height'))
                        or not -.1<=s['x']<=s['end_x']<=page['width']+.1 or not -.1<=s['y']<=page['height']+.1 or not 0<s['font_height']<=100):
                    raise SourcePdfError('invalid_worker_result')
        if count>CHAR_LIMIT:raise SourcePdfError('character_limit')
        if time.monotonic()>=deadline:raise SourcePdfError('timeout')
        return result
    except SourcePdfError as e:e.content_sha256=digest;raise
    except (OSError,ValueError,TypeError,KeyError,OverflowError):raise SourcePdfError('invalid_worker_result',content_sha256=digest)from None
