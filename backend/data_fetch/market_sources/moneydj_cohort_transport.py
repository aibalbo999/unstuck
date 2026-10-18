"""One capped ordinary HTTPS GET for the public MoneyDJ cohort page."""
from __future__ import annotations

import json
import os
import time

import httpx

from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import SourceResponseError, observe_http_response
from .construction_cohort_transport import _headers
from .moneydj_peer_cohort import URL, PROVIDER, MAX_BYTES

PROXY_ENV=("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy")


def download_html(*, deadline, diagnostics=None):
    diagnostics=diagnostics if diagnostics is not None else {}
    diagnostics["http_request_sent"]=False
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK")=="1":
        raise SourceResponseError("test_network_disabled")
    if proxy_url_for_request(URL,PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
        raise SourceResponseError("proxy_configuration_unsupported")
    remaining=min(7.,deadline-time.monotonic())
    if remaining<=0:
        raise SourceResponseError("timeout")
    end=min(deadline,time.monotonic()+remaining)
    argv=["/usr/bin/curl","--disable","--silent","--max-time",str(remaining),
          "--connect-timeout",str(min(3.,remaining)),"--max-filesize",str(MAX_BYTES),
          "--proto","=https","--max-redirs","0","--retry","0",
          "--dump-header","/dev/fd/{HEADER_FD}","--write-out","%{stderr}%{json}",URL]
    parts,rc,error=collect_capped_process(argv,end,body_limit=MAX_BYTES,headers=True)
    diagnostics["http_request_sent"]=bool(parts.get("process_started"))
    status,headers=_headers(parts["headers"])
    try:meta=json.loads(parts["metadata"])
    except (ValueError,UnicodeDecodeError):meta={}
    meta=meta if isinstance(meta,dict) else {}
    if status is None and type(meta.get("http_code")) is int and 200<=meta["http_code"]<=599:
        status=meta["http_code"]
    response=httpx.Response(status,headers=headers,request=httpx.Request("GET",URL)) if status else None
    if response is not None:observe_http_response(response)
    def fail(kind):
        exc=SourceResponseError(kind,status_code=status)
        if response is not None:exc.response=response
        raise exc
    if status is not None and status!=200:
        fail({401:"authentication",403:"access_denied",429:"rate_limited"}.get(status,"server_error" if status>=500 else "http_error"))
    if error or rc:
        fail(error or ("timeout" if rc==28 else "response_too_large" if rc==63 else "transport_error"))
    if (status!=200 or meta.get("http_code")!=status or meta.get("url_effective")!=URL
            or meta.get("num_redirects")!=0):
        fail("transport_metadata_invalid")
    if headers.get("content-encoding","identity").lower() not in ("","identity"):
        fail("unsupported_content_encoding")
    if headers.get("content-type","").split(";")[0].strip().lower() not in {"text/html","application/xhtml+xml"}:
        fail("unexpected_content_type")
    if time.monotonic()>=deadline:
        fail("timeout")
    return parts["body"]
