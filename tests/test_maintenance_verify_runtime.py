"""Own-socket lifecycle tests with fake sockets/server; no listener is started."""
import builtins
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def runtime(monkeypatch):
    spec=importlib.util.spec_from_file_location('maintenance_cli_probe',ROOT/'scripts/maintenance_verify.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    monkeypatch.delenv('LAN_ACCESS',raising=False)
    state={'bound':False,'events':[],'configs':[],'action':None}
    class Socket:
        def __init__(self,*args):self.owned=False;state['events'].append('socket_created')
        def __enter__(self):return self
        def bind(self,address):
            assert address==('127.0.0.1',8080)
            if state['bound']:raise OSError('address in use')
            self.owned=True;state['bound']=True;state['events'].append('bound_own_socket')
        def __exit__(self,*args):
            state['events'].append('closed_own_socket' if self.owned else 'closed_unbound_socket')
            if self.owned:state['bound']=False
    def config(app,**kwargs):state['configs'].append(kwargs);return app
    class Server:
        started=True
        def __init__(self,config):state['events'].append('server_constructed')
        def run(self,*,sockets):
            assert len(sockets)==1 and sockets[0].owned
            state['events'].append('server_run')
            if state['action']:state['action']()
    monkeypatch.setattr(cli,'socket',SimpleNamespace(AF_INET=2,SOCK_STREAM=1,socket=Socket))
    monkeypatch.setitem(sys.modules,'uvicorn',SimpleNamespace(Config=config,Server=Server))
    return cli,state,Server


@pytest.mark.parametrize('args',[[],['--maintenance-verify','extra'],['--port','8081'],['--maintenance-verify=1']])
def test_direct_entry_requires_exact_opt_in_before_creating_socket(runtime,args):
    cli,state,_=runtime
    assert cli.main(args)==64 and state['events']==[]


def test_inherited_lan_configuration_is_rejected_even_when_invoked_directly(runtime,monkeypatch):
    cli,state,_=runtime;monkeypatch.setenv('LAN_ACCESS','1')
    assert cli.main(['--maintenance-verify'])==64 and state['events']==[]


def test_config_is_single_local_server_and_ignores_uvicorn_environment(runtime,monkeypatch):
    cli,state,_=runtime
    for k,v in {'WEB_CONCURRENCY':'99','UVICORN_RELOAD':'true','UVICORN_HOST':'0.0.0.0','UVICORN_PORT':'9999'}.items():monkeypatch.setenv(k,v)
    assert cli.main(['--maintenance-verify'])==0
    options=state['configs'][0]
    assert options['workers']==1 and options['reload'] is False and options['host']=='127.0.0.1' and options['port']==8080
    assert options['ws']=='none' and options['proxy_headers'] is False and options['lifespan']=='on'
    assert state['events']==['socket_created','bound_own_socket','server_constructed','server_run','closed_own_socket']


def test_occupied_port_does_not_construct_server_or_touch_existing_owner(runtime):
    cli,state,_=runtime;state['bound']=True
    assert cli.main(['--maintenance-verify'])==1
    assert state['bound'] is True and state['configs']==[]
    assert state['events']==['socket_created','closed_unbound_socket']


def test_repeated_start_preserves_first_listener(runtime):
    cli,state,_=runtime
    def overlap():
        assert cli.main(['--maintenance-verify'])==1
        assert state['bound'] is True
    state['action']=overlap
    assert cli.main(['--maintenance-verify'])==0
    assert state['events'].count('server_run')==1
    assert state['events'].count('closed_own_socket')==1


@pytest.mark.parametrize('error',[KeyboardInterrupt(),SystemExit(1),RuntimeError('server failed')])
def test_shutdown_or_error_closes_only_new_socket_without_fallback(runtime,error):
    cli,state,_=runtime
    def fail():raise error
    state['action']=fail
    if isinstance(error,KeyboardInterrupt):assert cli.main(['--maintenance-verify'])==130
    else:
        with pytest.raises(type(error)):cli.main(['--maintenance-verify'])
    assert state['bound'] is False and state['events'][-1]=='closed_own_socket'
    assert state['events'].count('server_run')==1


def test_missing_dependency_closes_socket_and_never_installs(runtime,monkeypatch):
    cli,state,_=runtime;original=builtins.__import__
    def imports(name,*args,**kwargs):
        if name=='uvicorn':raise ImportError('missing')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',imports)
    assert cli.main(['--maintenance-verify'])==69
    assert state['events']==['socket_created','bound_own_socket','closed_own_socket']


def test_failed_lifespan_does_not_report_success(runtime):
    cli,state,server=runtime;server.started=False
    assert cli.main(['--maintenance-verify'])==1 and state['bound'] is False


def test_installed_uvicorn_accepts_configuration_without_starting_any_service(monkeypatch):
    import socket
    import uvicorn
    spec=importlib.util.spec_from_file_location('maintenance_real_config_probe',ROOT/'scripts/maintenance_verify.py')
    cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
    monkeypatch.delenv('LAN_ACCESS',raising=False)
    configs=[]
    class Socket:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def bind(self,address):assert address==('127.0.0.1',8080)
    class Server:
        started=True
        def __init__(self,config):config.load();configs.append(config)
        def run(self,**kwargs):assert 'sockets' in kwargs
    def forbidden(*args,**kwargs):raise AssertionError('Real socket operation forbidden')
    monkeypatch.setattr(socket.socket,'bind',forbidden)
    monkeypatch.setattr(socket.socket,'connect',forbidden)
    monkeypatch.setattr(cli,'socket',SimpleNamespace(AF_INET=2,SOCK_STREAM=1,socket=lambda *args:Socket()))
    monkeypatch.setattr(uvicorn,'Server',Server)
    assert cli.main(['--maintenance-verify'])==0
    assert len(configs)==1 and configs[0].loaded and configs[0].workers==1
    assert configs[0].loaded_app.__class__.__name__=='MaintenanceApplication'
