"""A completed bounded parser may use a conservative OS child-peak bound."""
from types import SimpleNamespace
from pathlib import Path
import resource
import subprocess
import sys
import pytest
import source_pdf_reader as reader
from test_source_pdf_reader import make_pdf


def exit_race(monkeypatch,*,sample_reason='memory_accounting_unavailable'):
    original_popen=subprocess.Popen
    original_command=reader._worker_command
    processes=[]
    class ExitVisibilityLag:
        def __init__(self,*a,**k):
            self.child=original_popen(*a,**k);self.lag=False
        def __getattr__(self,key):return getattr(self.child,key)
        def poll(self):
            if self.lag:self.lag=False;return None
            return self.child.poll()
        def wait(self,*a,**k):return self.child.wait(*a,**k)
    def spawn(*a,**k):
        p=ExitVisibilityLag(*a,**k);processes.append(p);return p
    worker=Path(reader.__file__).with_name('source_pdf_worker.py')
    code=f"import time,sys,runpy;time.sleep(.05);sys.argv=[{str(worker)!r},sys.argv[1]];runpy.run_path({str(worker)!r},run_name='__main__')"
    monkeypatch.setattr(reader.subprocess,'Popen',spawn)
    monkeypatch.setattr(reader,'_worker_command',lambda deadline:[sys.executable,'-B','-c',code,str(deadline)])
    calls=[]
    def sample(pid):
        calls.append(pid)
        if len(calls)==1:return 0
        p=processes[0]
        assert p.child.wait(timeout=3)==0
        p.lag=True
        raise reader.SourcePdfError(sample_reason)
    monkeypatch.setattr(reader,'_memory_sampler',lambda:sample)
    return processes,calls


def test_completed_parser_with_kernel_bound_is_not_a_false_failure(monkeypatch):
    monkeypatch.setattr(reader.sys,'platform','darwin')
    monkeypatch.setattr(resource,'getrusage',lambda who:SimpleNamespace(ru_maxrss=32*1024*1024))
    processes,calls=exit_race(monkeypatch)
    result=reader.extract_pdf_pages(make_pdf([b'Actual original 123.45']))
    assert result['pages'][0]['text']=='Actual original 123.45'
    assert len(calls)==2 and processes[0].returncode==0


@pytest.mark.parametrize('peak,reason',[(0,'memory_accounting_unavailable'),(-1,'memory_accounting_unavailable'),
    (None,'memory_accounting_unavailable'),(True,'memory_accounting_unavailable'),
    (float('nan'),'memory_accounting_unavailable'),(float('inf'),'memory_accounting_unavailable'),
    (reader.MEMORY_LIMIT+1,'memory_limit')])
def test_missing_invalid_or_over_limit_kernel_bound_still_rejects(monkeypatch,peak,reason):
    monkeypatch.setattr(reader.sys,'platform','darwin')
    monkeypatch.setattr(resource,'getrusage',lambda who:SimpleNamespace(ru_maxrss=peak))
    exit_race(monkeypatch)
    with pytest.raises(reader.SourcePdfError,match=reason):
        reader.extract_pdf_pages(make_pdf([b'Original']))


def test_other_sampler_failures_are_not_hidden_by_an_exited_child(monkeypatch):
    monkeypatch.setattr(reader.sys,'platform','darwin')
    monkeypatch.setattr(resource,'getrusage',lambda who:SimpleNamespace(ru_maxrss=32*1024*1024))
    exit_race(monkeypatch,sample_reason='resource_limits_unavailable')
    with pytest.raises(reader.SourcePdfError,match='resource_limits_unavailable'):
        reader.extract_pdf_pages(make_pdf([b'Original']))


@pytest.mark.skipif(sys.platform!='darwin',reason='Darwin kernel accounting integration')
def test_real_reaped_child_is_covered_by_the_darwin_peak_counter(monkeypatch):
    processes,calls=exit_race(monkeypatch)
    result=reader.extract_pdf_pages(make_pdf([b'Native kernel evidence']))
    assert result['coverage_status']=='complete' and len(calls)==2
    assert 0<resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss<=reader.MEMORY_LIMIT


def test_ignored_child_signal_keeps_peak_accounting_closed(monkeypatch):
    import signal
    monkeypatch.setattr(reader.sys,'platform','darwin')
    old=signal.getsignal
    monkeypatch.setattr(signal,'getsignal',lambda sig:signal.SIG_IGN if sig==signal.SIGCHLD else old(sig))
    monkeypatch.setattr(resource,'getrusage',lambda who:SimpleNamespace(ru_maxrss=32*1024*1024))
    exit_race(monkeypatch)
    with pytest.raises(reader.SourcePdfError,match='memory_accounting_unavailable'):
        reader.extract_pdf_pages(make_pdf([b'Original']))
