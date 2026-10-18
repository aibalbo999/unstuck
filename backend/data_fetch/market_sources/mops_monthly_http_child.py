"""Ordinary httpx POST used only by the public MOPS monthly JSON endpoint.

The parent caps output and kills/reaps this child at its shared deadline.
No browser impersonation, cookies, redirects, retries or credential headers.
"""
import json
import os
import sys

import httpx

URL = "https://mops.twse.com.tw/mops/api/t05st01"
ALLOWED_URLS = {URL, "https://mops.twse.com.tw/mops/api/t59sb01_detail",
               "https://mops.twse.com.tw/mops/api/t05st01_detail"}


def main():
    url, form, header_fd, remaining = sys.argv[1:]
    if url not in ALLOWED_URLS:
        return 2
    try:
        with httpx.Client(timeout=float(remaining), follow_redirects=False, trust_env=False) as client:
            with client.stream("POST", url, json=json.loads(form),
                               headers={"Referer": "https://mops.twse.com.tw/mops/", "Accept-Encoding": "identity"}) as response:
                headers = f"HTTP/1.1 {response.status_code}\r\n"
                headers += "".join(f"{key}: {value}\r\n" for key, value in response.headers.items()
                                   if key.lower() in {"content-type", "content-encoding", "retry-after"})
                os.write(int(header_fd), (headers + "\r\n").encode("latin-1"))
                for chunk in response.iter_raw():
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                sys.stderr.write(json.dumps({"http_code": response.status_code,
                                             "url_effective": str(response.url), "num_redirects": 0}))
        return 0
    except Exception as exc:
        sys.stderr.write(json.dumps({"error_kind": "timeout" if isinstance(exc, httpx.TimeoutException) else "transport_error"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
