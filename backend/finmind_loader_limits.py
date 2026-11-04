"""Per-owned-loader synchronous SDK limits, without global SDK monkeypatches.

The installed synchronous get_data ignores its max_retry_times argument. Bind a
private copy of that same function to this loader, injecting one helper attempt.
The project resilience layer owns further retries. Socket bounds include login;
they are not a wall-clock or OS DNS deadline.
"""
from contextvars import ContextVar
from contextlib import contextmanager
from functools import wraps
import inspect
import math
from types import FunctionType,MethodType
import requests

CONNECT_SECONDS=3.0
READ_SECONDS=5.0
_FAILURE=ContextVar('finmind_owned_request_failure',default=None)
_EXISTING_PER_BUDGET=ContextVar('finmind_existing_per_budget',default=False)

@contextmanager
def existing_per_socket_budget():
    """Only the existing single-send PER workflow retains its explicit12s."""
    token=_EXISTING_PER_BUDGET.set(True)
    try:yield
    finally:_EXISTING_PER_BUDGET.reset(token)

class UnsupportedFinMindSdkError(RuntimeError):
    retryable=False

class NativeSdkHTTPError(requests.HTTPError):
    """Actual native response retained; credentials/body never enter str()."""

class NativeSdkTransportError(requests.RequestException):
    http_status_observed=False

class _QuietSdkLogger:
    def __getattr__(self,_):return lambda *a,**k:None

def _timeout(value):
    def cap(v,maximum):
        if v is None:return maximum
        if type(v)not in(int,float)or not math.isfinite(v)or v<=0:raise ValueError('Invalid native SDK timeout')
        return min(float(v),maximum)
    if _EXISTING_PER_BUDGET.get()and value is not None:
        if isinstance(value,tuple):
            if len(value)!=2:raise ValueError('Invalid native SDK timeout tuple')
            return cap(value[0],12.),cap(value[1],12.)
        return cap(value,12.)
    if isinstance(value,tuple):
        if len(value)!=2:raise ValueError('Invalid native SDK timeout tuple')
        return cap(value[0],CONNECT_SECONDS),cap(value[1],READ_SECONDS)
    return cap(value,CONNECT_SECONDS),cap(value,READ_SECONDS)

def _clone(method,**changes):
    f=method.__func__;namespace=dict(f.__globals__);namespace.update(changes,logger=_QuietSdkLogger())
    copy=FunctionType(f.__code__,namespace,f.__name__,f.__defaults__,f.__closure__)
    copy.__kwdefaults__=f.__kwdefaults__;copy.__annotations__=dict(f.__annotations__)
    copy.__module__=f.__module__;copy.__qualname__=f.__qualname__
    return MethodType(copy,method.__self__)

def install_loader_limits(loader):
    """Change this SDK-owned instance only; never SDK modules or Session class."""
    session=getattr(loader,'_FinMindApi__session',None)
    if type(session)is not requests.Session:return False
    if getattr(session,'_stock_sdk_limits_installed',False):return True
    original=session.request
    if getattr(original,'__func__',None)is not requests.Session.request:
        raise UnsupportedFinMindSdkError('Unknown SDK-owned request implementation')
    @wraps(original)
    def bounded_request(*args,**kwargs):
        kwargs['timeout']=_timeout(kwargs.get('timeout'))
        kwargs['allow_redirects']=False
        try:
            response=original(*args,**kwargs)
        except requests.RequestException as cause:
            error=NativeSdkTransportError('Native FinMind transport failed ('+type(cause).__name__+')',
                request=getattr(cause,'request',None),response=getattr(cause,'response',None))
            if isinstance(error.response,requests.Response):error.http_status_observed=True
            box=_FAILURE.get()
            if box is not None:box.append(error)
            raise error from cause
        if type(response.status_code)is not int or response.status_code!=200:
            error=NativeSdkHTTPError('Native FinMind HTTP status '+str(response.status_code),request=response.request,response=response)
            box=_FAILURE.get()
            if box is not None:box.append(error)
            raise error
        return response
    session.request=bounded_request
    method=getattr(loader,'get_data',None)
    is_sdk=any(c.__module__.startswith('FinMind.')for c in type(loader).__mro__)
    if is_sdk:
        f=getattr(method,'__func__',None)
        helper=f.__globals__.get('request_get')if f is not None else None
        if (f is None or f.__module__!='FinMind.data.finmind_api'or 'request_get'not in f.__code__.co_names
                or not callable(helper)or helper.__module__!='FinMind.utility.request'
                or 'max_retry_times'not in inspect.signature(helper).parameters):
            raise UnsupportedFinMindSdkError('Unsupported synchronous native SDK request contract')
        signature=inspect.signature(helper)
        @wraps(helper)
        def single_request(*args,**kwargs):
            bound=signature.bind(*args,**kwargs);bound.apply_defaults();bound.arguments['max_retry_times']=1
            bound.arguments['timeout']=_timeout(bound.arguments.get('timeout'))
            token=_FAILURE.set([])
            try:
                result=helper(*bound.args,**bound.kwargs)
                errors=_FAILURE.get()
                if errors:raise errors[0]  # SDK may have swallowed the actual request failure.
                return result
            finally:_FAILURE.reset(token)
        cloned=_clone(method,request_get=single_request);get_signature=inspect.signature(cloned)
        @wraps(cloned)
        def synchronous_data(*args,**kwargs):
            arguments=get_signature.bind(*args,**kwargs)
            if arguments.arguments.get('use_async',False)is not False:
                raise UnsupportedFinMindSdkError('Native SDK async transport is outside this synchronous source contract')
            return cloned(*args,**kwargs)
        loader.get_data=synchronous_data
        login=getattr(loader,'login_by_token',None)
        if getattr(getattr(login,'__func__',None),'__module__',None)=='FinMind.data.finmind_api':
            loader.login_by_token=_clone(login)
    session._stock_sdk_limits_installed=True
    return True

def call_native_login(method,*args,**kwargs):
    """Same SDK login and token; suppress only its per-method diagnostics."""
    if getattr(getattr(method,'__func__',None),'__module__',None)=='FinMind.data.finmind_api':
        method=_clone(method)
    return method(*args,**kwargs)
