"""Public format boundary tests; synthetic bodies are never acquisition evidence."""
from datetime import date
import io
import json
import zipfile
import pytest
from free_macro_original_parsers import cboe_vix, bls_cpi, fed_h15

ASOF = date(2026, 11, 1)

def cpi(series="CUSR0000SA0", latest="104", prior="100"):
    return json.dumps({"status":"REQUEST_SUCCEEDED", "Results":{"series":[{
        "seriesID":series, "data":[
            {"year":"2026", "period":"M09", "value":latest},
            {"year":"2025", "period":"M09", "value":prior}]}]}}).encode()

def h15(instrument="TCMNOM", frequency="9", unit="Percent:_Per_Year"):
    xml = (f'<Root><Series CURRENCY="NA" FREQ="{frequency}" INSTRUMENT="{instrument}" '
           f'MATURITY="Y10" SERIES_NAME="RIFLGFCY10_N.B" UNIT="{unit}" UNIT_MULT="1">'
           '<Obs TIME_PERIOD="2026-10-30" OBS_STATUS="A" OBS_VALUE="4.5"/>'
           '</Series></Root>').encode()
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        z.writestr("H15_data.xml", xml)
    return stream.getvalue()

def test_vix_close_is_not_open():
    r = cboe_vix(b"DATE,OPEN,HIGH,LOW,CLOSE\n10/30/2026,18,21,17,20\n", ASOF)
    assert r["value"] == 20 and r["price_field"] == "CLOSE"
    assert r["historical_pit_verified"] is False

@pytest.mark.parametrize("raw", [
    b"DATE,OPEN,HIGH,LOW,CLOSE\n10/30/2026,18,21,17,NaN\n",
    b"DATE,OPEN,HIGH,LOW,CLOSE\n10/30/2026,18,19,17,20\n",
    b"DATE,OPEN,HIGH,LOW,CLOSE\n11/30/2026,18,21,17,20\n",
    b"DATE,OPEN,HIGH,LOW,CLOSE\n09/30/2026,18,21,17,20\n",
    b"DATE,OPEN,HIGH,LOW,CLOSE\n10/30/2026,18,21,17,20\n10/30/2026,18,21,17,20\n"])
def test_bad_vix_fails_closed(raw):
    with pytest.raises(ValueError): cboe_vix(raw, ASOF)

def test_cpi_exact_same_month():
    r = bls_cpi(cpi(), ASOF)
    assert r["value"] == pytest.approx(4)
    assert r["date"] == "2026-09-01" and r["prior_date"] == "2025-09-01"
    assert r["seasonal_adjustment"] == "seasonally_adjusted"

@pytest.mark.parametrize("series", ["CUUR0000SA0", "CUSR0000SA0L1", "VIXCLS"])
def test_cpi_series_identity(series):
    with pytest.raises(ValueError): bls_cpi(cpi(series=series), ASOF)

@pytest.mark.parametrize("latest,prior", [("-","100"),("104","-"),("104","0"),("NaN","100")])
def test_missing_or_nonfinite_cpi_not_substituted(latest,prior):
    with pytest.raises(ValueError): bls_cpi(cpi(latest=latest,prior=prior),ASOF)

def test_other_month_does_not_replace_missing_prior():
    body=json.loads(cpi());body["Results"]["series"][0]["data"][1]["period"]="M08"
    with pytest.raises(ValueError):bls_cpi(json.dumps(body).encode(),ASOF)

def test_duplicate_cpi_rejected():
    body=json.loads(cpi());rows=body["Results"]["series"][0]["data"];rows.append(dict(rows[0]))
    with pytest.raises(ValueError):bls_cpi(json.dumps(body).encode(),ASOF)

def test_nominal_daily_ten_year_yield():
    r=fed_h15(h15(),ASOF)
    assert r["value"] == 4.5 and r["frequency"] == "daily"

@pytest.mark.parametrize("kwargs", [{"instrument":"TCMII"},{"frequency":"21"},{"unit":"Index"}])
def test_wrong_fed_dimensions(kwargs):
    with pytest.raises(ValueError):fed_h15(h15(**kwargs),ASOF)

def test_xml_entity_rejected():
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w") as z:z.writestr("H15_data.xml",b'<!DOCTYPE Root [<!ENTITY x "x">]><Root/>')
    with pytest.raises(ValueError):fed_h15(stream.getvalue(),ASOF)


def test_utf16_entities_are_not_accepted():
    with zipfile.ZipFile(io.BytesIO(h15())) as source:
        template=source.read("H15_data.xml").decode()
    xml='<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE Root [<!ENTITY x "4.5">]>'+template.replace('OBS_VALUE="4.5"','OBS_VALUE="&x;"')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,"w") as z:z.writestr("H15_data.xml",xml.encode("utf-16"))
    with pytest.raises(ValueError):fed_h15(stream.getvalue(),ASOF)


def test_duplicate_inactive_fed_date_rejected():
    from free_macro_original_parsers import fed_series, FED_ATTRIBUTES
    rows=[{"TIME_PERIOD":"2026-10-30","OBS_STATUS":"ND","OBS_VALUE":"ND"},
          {"TIME_PERIOD":"2026-10-30","OBS_STATUS":"A","OBS_VALUE":"4.5"}]
    with pytest.raises(ValueError):fed_series(dict(FED_ATTRIBUTES),rows,ASOF)


@pytest.mark.parametrize("parser", [cboe_vix,bls_cpi,fed_h15])
def test_empty_original_rejected(parser):
    with pytest.raises(ValueError):parser(b"",ASOF)
