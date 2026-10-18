"""Historical chart compatibility must not trust arbitrary artifact scripts."""
import base64
import hashlib

import pytest

from test_report_chart_security_policy import ScriptCollector, report_route_response, sample_report, script_hash

LEGACY_HASH = '+X8W7FUAJhbVe/HkS6EEIAsw9b3F02bOCn0s9wvFqFU='


def legacy_report():
    html=sample_report()
    for line in (
        '            netRevenue: chartNumberSeries(parsed.netRevenue),\n',
        '            incomeSeries: Array.isArray(parsed.incomeSeries) ? chartNumberSeries(parsed.incomeSeries) : null,\n',
        "            incomeLabel: typeof parsed.incomeLabel === 'string' ? parsed.incomeLabel : null,\n",
        '            netRevenueMargin: Array.isArray(parsed.netRevenueMargin) ? chartNumberSeries(parsed.netRevenueMargin) : null,\n',
        "            netMarginLabel: typeof parsed.netMarginLabel === 'string' ? parsed.netMarginLabel : null,\n",
        "            netIncomeLabel: typeof parsed.netIncomeLabel === 'string' ? parsed.netIncomeLabel : null,\n",
    ):
        html=html.replace(line,'')
    for current,old in (
        ("label: CHART_DATA.incomeLabel || '年度營收'","label: '年度營收'"),
        ('data: CHART_DATA.incomeSeries || CHART_DATA.revenue','data: CHART_DATA.revenue'),
        ("label: CHART_DATA.netIncomeLabel || '淨利'","label: '淨利'"),
        ("label: CHART_DATA.netMarginLabel || '淨利率'","label: '淨利率'"),
        ('data: CHART_DATA.netRevenueMargin || CHART_DATA.netMargin','data: CHART_DATA.netMargin'),
    ):html=html.replace(current,old)
    scripts=ScriptCollector();scripts.feed(html)
    runtime=next(s['text'] for s in scripts.scripts if not s['attrs'])
    assert base64.b64encode(hashlib.sha256(runtime.encode()).digest()).decode()==LEGACY_HASH
    return html


@pytest.mark.parametrize('suffix',['','/download/html'])
def test_known_legacy_charts_are_served_with_the_canonical_runtime(tmp_path,suffix):
    html=legacy_report(); malicious='window.untrustedReport=true'
    response=report_route_response(tmp_path,html+'<script>'+malicious+'</script>',suffix)
    parser=ScriptCollector();parser.feed(sample_report())
    canonical=next(s['text'] for s in parser.scripts if not s['attrs'])
    policy=response.headers['content-security-policy']
    assert script_hash(canonical) in policy
    assert "'sha256-"+LEGACY_HASH+"'" not in policy
    assert script_hash(malicious) not in policy
    assert canonical in response.text
    assert "script-src-attr 'none'" in policy
    assert "'unsafe-eval'" not in policy
    script_sources=next(part for part in policy.split(';') if part.strip().startswith('script-src '))
    assert "'unsafe-inline'" not in script_sources
    assert (tmp_path/'2330_TW_v4_report_20260104_010000.html').read_text()==html+'<script>'+malicious+'</script>'


def test_altered_legacy_runtime_is_not_upgraded(tmp_path):
    html=legacy_report().replace('const chartPayload','window.untrustedReport=true; const chartPayload')
    response=report_route_response(tmp_path,html,'')
    assert 'https://cdn.jsdelivr.net' not in response.headers['content-security-policy']
