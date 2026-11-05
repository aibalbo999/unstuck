from datetime import date
from copy import deepcopy
import pytest
from delta_press_fixtures import index,article,URL,TEXT
from data_fetch.market_sources.delta_press_parse import parse_article,index_cards

def test_inline_whole_body_not_caption():
    value=parse_article(index(),article(),URL,today=date(2026,11,5))
    assert value['text']==TEXT and value['publication_clock_and_timezone'] is None
    assert value['full30day_history_verified'] is False

@pytest.mark.parametrize('change',['partial','external','mount','date','caption'])
def test_wrong_or_incomplete_original_rejected(change):
    raw=article()
    if change=='partial':raw=raw[:-10]
    if change=='external':raw=raw.replace(b'<iframe ',b'<iframe src="https://example.com" ')
    if change=='mount':raw=raw.replace(b'$RC("B:0","S:0")',b'')
    if change=='date':raw=raw.replace(b'10/14/2026',b'10/13/2026')
    if change=='caption':raw=raw.replace(TEXT.encode(),b'captions')
    with pytest.raises(ValueError):parse_article(index(),raw,URL,today=date(2026,11,5))
