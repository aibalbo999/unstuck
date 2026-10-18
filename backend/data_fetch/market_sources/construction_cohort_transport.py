"""Capped ordinary HTTPS GETs for fixed TPEx construction/food cohort pages."""
from __future__ import annotations
import json
import os
import re
import time
import httpx
from bounded_curl_process import collect_capped_process
from external_http_client import proxy_url_for_request
from search_provider_runtime import SourceResponseError, observe_http_response

PROVIDER="TPEx construction industry-chain candidates"
ISSUER_URL="https://ic.tpex.org.tw/company_chain.php?stk_code=9945"
SEGMENT_URL="https://ic.tpex.org.tw/introduce.php?ic=S000"
FOOD_ISSUER_URL="https://ic.tpex.org.tw/company_chain.php?stk_code=1229"
FOOD_SEGMENT_URL="https://ic.tpex.org.tw/introduce.php?ic=M000"
BODY_LIMIT=250_000
PROXY_ENV=("HTTP_PROXY","HTTPS_PROXY","ALL_PROXY","http_proxy","https_proxy","all_proxy")

def _headers(raw):
    status=None
    headers={}
    for line in raw.replace(b"\r\n",b"\n").splitlines(keepends=True):
        if line.startswith(b"HTTP/"):
            m=re.match(rb"HTTP/\S+ +([2-5]\d{2})(?:[ \n]|$)",line)
            if m:status,headers=int(m[1]),{}
        elif status and line.endswith(b"\n"):
            key,sep,value=line.partition(b":")
            name=key.decode("ascii","ignore").lower()
            if sep and name in {"content-type","content-encoding","retry-after"}:
                headers[name]=value.decode("latin-1").strip()
    return status,headers

def download_html(url,*,deadline):
    if os.getenv("STOCK_AGENT_TEST_NO_NETWORK")=="1":
        raise SourceResponseError("test_network_disabled")
    if url not in (ISSUER_URL,SEGMENT_URL,FOOD_ISSUER_URL,FOOD_SEGMENT_URL):
        raise SourceResponseError("transport_url_invalid")
    if proxy_url_for_request(url,PROVIDER) or any(os.getenv(k) for k in PROXY_ENV):
        raise SourceResponseError("proxy_configuration_unsupported")
    remaining=min(6.,deadline-time.monotonic())
    if remaining<=0:
        raise SourceResponseError("timeout")
    end=min(deadline,time.monotonic()+remaining)
    argv=["/usr/bin/curl","--disable","--silent","--max-time",str(remaining),
          "--connect-timeout",str(min(3.,remaining)),"--max-filesize",str(BODY_LIMIT),
          "--proto","=https","--max-redirs","0","--retry","0",
          "--dump-header","/dev/fd/{HEADER_FD}","--write-out","%{stderr}%{json}",url]
    parts,rc,error=collect_capped_process(argv,end,body_limit=BODY_LIMIT,headers=True)
    status,headers=_headers(parts["headers"])
    try:meta=json.loads(parts["metadata"])
    except (ValueError,UnicodeDecodeError):meta={}
    meta=meta if isinstance(meta,dict) else {}
    if status is None and type(meta.get("http_code")) is int and 200<=meta["http_code"]<=599:
        status=meta["http_code"]
    response=httpx.Response(status,headers=headers,request=httpx.Request("GET",url)) if status else None
    if response is not None:observe_http_response(response)
    def fail(kind):
        exc=SourceResponseError(kind,status_code=status)
        if response is not None:exc.response=response
        raise exc
    # Preserve an actual refusal, including Retry-After, over a body failure.
    if status is not None and status!=200:
        fail({401:"authentication",403:"access_denied",429:"rate_limited"}.get(status,"server_error" if status>=500 else "http_error"))
    if error or rc:
        fail(error or ("timeout" if rc==28 else "response_too_large" if rc==63 else "transport_error"))
    if (status!=200 or meta.get("http_code")!=status or meta.get("url_effective")!=url
            or meta.get("num_redirects")!=0):
        fail("transport_metadata_invalid")
    if headers.get("content-encoding","identity").lower() not in ("","identity"):
        fail("unsupported_content_encoding")
    if headers.get("content-type","").split(";")[0].strip().lower() not in {"text/html","application/xhtml+xml"}:
        fail("unexpected_content_type")
    return parts["body"]
