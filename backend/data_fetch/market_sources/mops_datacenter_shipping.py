"""Staged issuer/period qualification; no inferred chart values or permissions."""
from datetime import date, datetime
import re
import unicodedata


def qualify(native, selected):
    if native['coverage_status'] != 'complete':
        raise ValueError('native presentation incomplete')
    texts=[re.sub(r'\s+',' ',p['text']).strip() for p in native['pages']]
    cover=texts[0];text=' '.join(texts)
    material=date.fromisoformat(selected['material_file_date'])
    event=date.fromisoformat(selected['event_date'])
    if selected['ticker']=='6669.TW':
        quarters=re.findall(r'\bIncome Statement (20\d{2}) Q([1-4])(?![-\d])\b',text)
        balance=re.findall(r'\bBalance Sheet (20\d{2}) Q([1-4])\b',text)
        title=re.findall(r'\b(20\d{2}) Q([1-4]) Financial Results\b',cover)
        dates=re.findall(r'\b([A-Z][a-z]+ \d{1,2}, 20\d{2})\b',cover)
        if len(quarters)!=1 or title!=quarters or balance!=quarters or len(dates)!=1:
            raise ValueError('quarterly financial scope ambiguous')
        year,q=map(int,quarters[0]);day=datetime.strptime(dates[0],'%B %d, %Y').date()
        if (q!=2 or day.year!=year or material.year!=year or event.year!=year
                or not date(year,6,30)<=day<=material<=event
                or f'Income Statement {year} Q1-Q2' not in text
                or f"{year%100:02}'Q2 % {year%100:02}'Q1 % QoQ% {(year-1)%100:02}'Q2" not in text
                or f"{year%100:02}'Q1~Q2 % {(year-1)%100:02}'Q1~Q2" not in text
                or 'IR@wiwynn.com' not in text or 'Wiwynn Confidential' not in cover
                or 'Copyright & Confidentiality Notice' not in cover
                or 'Any redistribution or reproduction' not in cover
                or 'express written permission' not in cover
                or any('NT$ millions' not in item for item in texts
                       if 'Income Statement' in item or 'Balance Sheet' in item)
                or 'This presentation is being delivered to the recipient.' not in text):
            raise ValueError('issuer date period or permission notice mismatch')
    elif selected['ticker']=='2606.TW':
        quarters=re.findall(r'\b(20\d{2})Q([1-4]) results highlights\b',text)
        meeting=re.findall(r'\bQ([1-4]) (20\d{2}) INVESTOR PRESENTATION\b',cover)
        dates=re.findall(r'\b([A-Z][a-z]{2} \d{1,2}, 20\d{2})\b',cover)
        if len(quarters)!=1 or len(meeting)!=1 or len(dates)!=1:
            raise ValueError('meeting and financial scopes ambiguous')
        year,q=map(int,quarters[0]);mq,my=map(int,meeting[0]);day=datetime.strptime(dates[0],'%b %d, %Y').date()
        normalized=unicodedata.normalize('NFKC',cover)
        if (q!=2 or my!=year or mq!=3 or day!=event or material>day
                or material.year!=year or day.year!=year or (day.month-1)//3+1!=mq
                or not re.search(fr'{my}\s*年第\s*{mq}\s*季法說會',cover)
                or f'{year}年第2季營運暨財務概況' not in text
                or 'NT$m unless otherwise noted' not in text
                or f'2Q{year%100:02} 1Q{year%100:02} 2Q{(year-1)%100:02}' not in text
                or not re.search(r'2606TT\.\s*SINCE\s+1984\.\s*TAIPEI',normalized)
                or 'IR@mail.uming.com.tw' not in text
                or 'This presentation contains forward-looking statements.' not in text
                or 'without independent verification' not in text):
            raise ValueError('issuer meeting financial period or disclaimer mismatch')
    else:
        raise ValueError('unqualified issuer')
    if date(year,6,30)>material:
        raise ValueError('financial period after material date')
    return f'{year}Q{q}'
