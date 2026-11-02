from datetime import datetime,date,timedelta,timezone
from html import escape
import pytest
from data_fetch.market_sources import walsin_conference as source
from data_fetch.market_sources.walsin_conference_transport import PDF_URL
NOW=datetime(2026,11,2,14,tzinfo=timezone.utc).timestamp()


def index(*,future='2026-11-06',old_pdf=PDF_URL,new_pdf=False,newer_history=False,empty_placeholder_links=False):
    current_pdf='<a href="https://www.walsin.com/new.pdf">Presentation</a>' if new_pdf else 'Presentation'
    if empty_placeholder_links:current_pdf='<a href="">Presentation</a>'
    fields={'Event Title':'Quarterly Conference Info','Event Date':future,'Event Time':'4:00 pm Taipei Time Zone','Video Link':'Upcoming conference','Conference Files':'<a href="https://wms.gridow.com/ir/walsin/walsin_26Q3.html">Conference call</a> | '+current_pdf+(' | <a href="">Press Release</a>'if empty_placeholder_links else' | Press Release')}
    rows=''.join('<tr><td>'+k+'</td><td>'+v+'</td></tr>'for k,v in fields.items())
    history='<tr><td>2026/08/07</td><td>4:00 pm</td><td>2Q26 Investor Conference Call</td><td><a href="'+escape(old_pdf)+'">Presentation</a></td></tr>'
    for i in range(30):history+='<tr><td>'+(date(2026,8,6)-timedelta(days=i)).strftime('%Y/%m/%d')+'</td><td>4:00 pm</td><td>Older event</td><td></td></tr>'
    if newer_history:history+='<tr><td>2026/10/01</td><td>4:00 pm</td><td>Newer event</td><td></td></tr>'
    return ('<html><head><title>Investor Conference – Walsin Lihwa</title></head><body><div id="investor-conference-tabContent"><div id="pills-investor-conference"><h3>Quarterly Conference Info</h3><table><tbody>'+rows+'</tbody></table></div></div><div id="pills-investor-conference-history"><table><tbody>'+history+'</tbody></table></div></body></html>').encode()


def test_upcoming_unpublished_event_does_not_hide_existing_qualified_material(monkeypatch):
    monkeypatch.setattr(source.time,'time',lambda:NOW)
    selected=source.select_presentation(index(),NOW)
    assert selected['period_label']=='2026Q2' and selected['event_date']=='2026-08-07'
    assert selected['pdf_url']==PDF_URL
    assert selected['upcoming_event_date']=='2026-11-06'
    assert selected['upcoming_presentation_available'] is False
    assert selected['selection_policy']=='qualified_historical_original_before_unpublished_future_event'

@pytest.mark.parametrize('change',[{'future':'2026-11-01'},{'future':'2027-11-06'},{'old_pdf':'https://other.example/q2.pdf'},{'new_pdf':True},{'newer_history':True}])
def test_unqualified_newer_material_or_completed_event_cannot_be_hidden(monkeypatch,change):
    monkeypatch.setattr(source.time,'time',lambda:NOW)
    with pytest.raises(ValueError):source.select_presentation(index(**change),NOW)


def test_empty_presentation_and_release_links_are_not_published_documents(monkeypatch):
    monkeypatch.setattr(source.time,'time',lambda:NOW)
    selected=source.select_presentation(index(empty_placeholder_links=True),NOW)
    assert selected['period_label']=='2026Q2' and selected['upcoming_presentation_available']is False
