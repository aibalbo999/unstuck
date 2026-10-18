from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from data_fetch.market_sources.tpex_company_history import fetch_recent_tpex_announcements
from data_fetch.provider_registry import ProviderRegistry
from data_fetch.types import FetchRequest
from news_freshness_policy import apply_news_freshness


NOW = datetime(2026, 10, 9, 3, 0, tzinfo=ZoneInfo("Asia/Taipei"))
INDEX = "https://mopsov.twse.com.tw/mops/web/t05st01"


def _index(*, code="5314", kind="otc", day="115/10/02", title="公告本公司董事會決議修正限制員工權利新股發行辦法"):
    spoke_date = str(int(day.split('/')[0]) + 1911) + ''.join(day.split('/')[1:])
    return ("<html><table class='hasBorder'><tr><th>公司代號</th><th>公司名稱</th><th>發言日期</th>"
            "<th>發言時間</th><th>主旨</th></tr><tr><td>" + code + "</td><td>世紀*</td>"
            f"<td>{day}</td><td>15:53:17</td><td>{title}</td>"
            "<td><input onclick=\"document.t05st01_fm.seq_no.value='1';"
            "document.t05st01_fm.spoke_time.value='155317';"
            f"document.t05st01_fm.spoke_date.value='{spoke_date}';"
            f"document.t05st01_fm.co_id.value='{code}';"
            f"document.t05st01_fm.TYPEK.value='{kind}';\"/></td></tr></table></html>")


def _detail(*, code="5314", body="本公司董事會決議修正一百一十五年限制員工權利新股發行辦法，詳如公告事項。"):
    return ("<html><table class='noBorder'><tr class='compName'><td>本資料由 (上櫃公司) "
            f"{code} 世紀* 公司提供</td></tr></table><table class='hasBorder'>"
            "<tr><th>序號</th><td>1</td><th>發言日期</th><td>115/10/02</td>"
            "<th>發言時間</th><td>15:53:17</td></tr>"
            "<tr><th>主旨</th><td>公告本公司董事會決議修正限制員工權利新股發行辦法</td></tr>"
            f"<tr><th>說明</th><td>{body}</td></tr></table></html>")


def _get(index_html, detail_html=None):
    calls = []
    def get(url, **kwargs):
        calls.append((url, kwargs.get('params')))
        request = httpx.Request('GET', url)
        return httpx.Response(200, request=request,
                              text=index_html if url == INDEX else detail_html or _detail())
    return get, calls


def test_tpex_history_uses_original_company_announcement_body():
    get, calls = _get(_index())
    rows, audit = fetch_recent_tpex_announcements("5314.TWO", now=NOW, get=get)
    assert audit["status"] == "success"
    assert audit["coverage_status"] == "window_complete"
    assert len(rows) == 1
    assert rows[0]["ticker"] == "5314.TWO"
    assert rows[0]["date"] == "2026-10-02T15:53:17+08:00"
    assert rows[0]["source_type"] == "official_disclosure"
    assert "限制員工權利" in rows[0]["text"]
    assert calls[0] == (INDEX, {"co_id": "5314", "year": "115", "firstin": "true", "step": "1"})
    assert len(calls) == 2


def test_wrong_market_or_issuer_index_does_not_fetch_detail():
    get, calls = _get(_index(kind="sii"))
    rows, audit = fetch_recent_tpex_announcements("5314.TWO", now=NOW, get=get)
    assert rows == []
    assert audit["rejected_reason_counts"] == {"invalid_detail_identity": 1}
    assert len(calls) == 1


def test_wrong_issuer_original_is_not_admitted():
    get, _ = _get(_index(), _detail(code="3324"))
    rows, audit = fetch_recent_tpex_announcements("5314.TWO", now=NOW, get=get)
    assert rows == []
    assert audit["rejected_reason_counts"] == {"detail_mismatch": 1}


def test_old_announcement_is_empty_evidence():
    get, calls = _get(_index(day="115/08/01"))
    rows, audit = fetch_recent_tpex_announcements("5314.TWO", now=NOW, get=get)
    assert rows == []
    assert audit["status"] == "unavailable"
    assert len(calls) == 1


def test_tpex_history_enters_recent_events_only_for_exact_market():
    get, _ = _get(_index())
    rows, _ = fetch_recent_tpex_announcements("5314.TWO", now=NOW, get=get)
    data = {"ticker": "5314.TWO", "company_name": "世紀*",
            "company_identity": {"official_name": "世紀*", "legal_name": "世紀民生科技股份有限公司"}}
    apply_news_freshness(data, cutoff=NOW, records=rows)
    assert len(data["recent_catalysts"]) == 1
    assert data["identity_rejected_catalysts"] == []
    registry = ProviderRegistry()
    assert "TPEx MOPS company announcement history" in registry.provider_names(
        FetchRequest.from_ticker("5314.TWO"), source="recent_catalysts")
    assert "TPEx MOPS company announcement history" not in registry.provider_names(
        FetchRequest.from_ticker("5314.TW"), source="recent_catalysts")


def test_tpex_infohub_originals_recover_mops_index_failure(monkeypatch):
    from data_fetch.market_sources import tpex_infohub

    recovered = [{"ticker": "5314.TWO", "date": "2026-10-08T12:00:00+08:00",
                  "title": "Official issuer update", "text": "Verified official statement",
                  "source": tpex_infohub.PROVIDER, "source_type": "official_disclosure"}]
    monkeypatch.setattr(tpex_infohub, "fetch_tpex_infohub_records",
                        lambda *_args, **_kwargs: (recovered, {"status": "success",
                            "actual_provider": tpex_infohub.PROVIDER, "record_count": 1}))

    def unavailable(*_args, **_kwargs):
        raise OSError("MOPS historical index unavailable")

    rows, audit = fetch_recent_tpex_announcements("5314.TWO", now=NOW, get=unavailable)

    assert rows == recovered
    assert audit["actual_provider"] == tpex_infohub.PROVIDER
    assert audit["fallback_from"]["status"] == "error"
