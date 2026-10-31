"""Run only fake interpreters; never invoke the normal launcher runtime."""
import json
import os
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]


def run_launcher(tmp_path, args, overrides=None):
    project=tmp_path/'project with spaces';project.mkdir()
    (project/'start_mac.command').write_bytes((ROOT/'start_mac.command').read_bytes())
    (project/'.venv/bin').mkdir(parents=True)
    (project/'scripts').mkdir()
    (project/'scripts/maintenance_verify.py').write_text('# test stub target\n')
    (project/'scripts/project_environment.sh').write_text('# successful storage preflight fixture\nreturn 0\n')
    log=tmp_path/'interpreter.log'
    interpreter=project/'.venv/bin/python'
    interpreter.write_text('''#!/bin/bash
printf '%s\\n' "$@" >> "$PROBE_LOG"
if [ "$1" = "-I" ] && [ "$2" = "-B" ] && [ "$3" = "$PROBE_ENTRY" ] && [ "$4" = "--maintenance-verify" ] && [ "$#" = 4 ]; then exit "${PROBE_EXIT:-0}"; fi
exit 97
''')
    interpreter.chmod(0o755)
    env={**os.environ,'LAN_ACCESS':'0','PROBE_LOG':str(log),'PROBE_ENTRY':str(project/'scripts/maintenance_verify.py')}
    env.pop('PYTHON_BIN',None)
    env.update(overrides or {})
    result=subprocess.run(['/bin/bash',str(project/'start_mac.command'),*args],env=env,capture_output=True,text=True,timeout=5)
    return result,log.read_text().splitlines() if log.exists() else [],project


def test_explicit_mode_executes_only_isolated_maintenance_entry(tmp_path):
    result,calls,project=run_launcher(tmp_path,['--maintenance-verify'])
    assert result.returncode==0,result.stdout+result.stderr
    assert calls==['-I','-B',str(project/'scripts/maintenance_verify.py'),'--maintenance-verify']
    assert not (project/'backend').exists()


@pytest.mark.parametrize('args',[['--maintenance'],['--maintenance-verify=0'],[''],['--maintenance-verify','extra'],['--maintenance-verify','--port','8081']])
def test_bad_mode_arguments_never_fall_through_to_normal_startup(tmp_path,args):
    result,calls,_=run_launcher(tmp_path,args)
    assert result.returncode==64 and calls==[]


@pytest.mark.parametrize('overrides',[{'LAN_ACCESS':'1'},{'LAN_ACCESS':'true'},{'LAN_ACCESS':'bad'},{'PYTHON_BIN':'/other/python'}])
def test_incompatible_mode_configuration_stops_before_interpreter(tmp_path,overrides):
    result,calls,_=run_launcher(tmp_path,['--maintenance-verify'],overrides)
    assert result.returncode==64 and calls==[]


def test_mode_failure_does_not_fall_through_or_install_anything(tmp_path):
    result,calls,_=run_launcher(tmp_path,['--maintenance-verify'],{'PROBE_EXIT':'42'})
    assert result.returncode==42 and len(calls)==4


def test_no_mode_argument_still_enters_original_startup_path(tmp_path):
    result,calls,_=run_launcher(tmp_path,[])
    # Fake interpreter aborts at the first original Python version probe.
    assert result.returncode==97 and calls==['-']
    assert '啟動 Wall Street AI' in result.stdout
