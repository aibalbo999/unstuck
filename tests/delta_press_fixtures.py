"""Synthetic published layout; no production acquisition claim."""
from html import escape
import json
URL='https://www.deltaww.com/en-US/press/41167'
TITLE='Delta published synthetic corporate statement'
SCRIPT='$RB=[];$RV=function(a){$RT=performance.now();for(var b=0;b<a.length;b+=2){var c=a[b],e=a[b+1];null!==e.parentNode&&e.parentNode.removeChild(e);var f=c.parentNode;if(f){var g=c.previousSibling,h=0;do{if(c&&8===c.nodeType){var d=c.data;if("/$"===d||"/&"===d)if(0===h)break;else h--;else"$"!==d&&"$?"!==d&&"$~"!==d&&"$!"!==d&&"&"!==d||h++}d=c.nextSibling;f.removeChild(c);c=d}while(c);for(;e.firstChild;)f.insertBefore(e.firstChild,c);g.data="$";g._reactRetry&&requestAnimationFrame(g._reactRetry)}}a.length=0};\n$RC=function(a,b){if(b=document.getElementById(b))(a=document.getElementById(a))?(a.previousSibling.data="$~",$RB.push(a,b),2===$RB.length&&("number"!==typeof $RT?requestAnimationFrame($RV.bind(null,$RB)):(a=performance.now(),setTimeout($RV.bind(null,$RB),2300>a&&2E3<a?2300-a:$RT+300-a)))):b.parentNode.removeChild(b)};$RC("B:0","S:0")'
TEXT='Delta, a global leader in power management and smart green solutions,'+' synthetic complete body.'*60

def page(url,content):
    return ('<html lang="en-US"><head><link rel="canonical" href="'+url+'"><meta property="og:url" content="'+url+'"><meta property="og:title" content="Press Center - '+TITLE+' - Delta"></head><body><main><template id="B:0"></template></main><div hidden id="S:0">'+content+'</div><script>'+SCRIPT+'</script></body></html>').encode()
def index():
    return page('https://www.deltaww.com/en-US/press','<h1>Press</h1><a href="'+URL+'"><span class="whitespace-pre-line">'+TITLE+'</span><div class="text-tag"><span>Corporate</span><span>10/14/2026</span></div></a>')
def article():
    inner='<html><head></head><body><p>'+TEXT+'</p></body></html>'
    return page(URL,'<div style="max-width:800px"><h1>'+TITLE+'</h1><iframe scrolling="no" srcdoc="'+escape(inner,quote=True)+'"></iframe><div><span>News Source: Brand and Communications</span><span>10/14/2026</span></div></div>')
def master():
    rows=[{'公司代號':str(8000+i),'公司名稱':f'合成樣本{i}股份有限公司','填補欄位':'x'*120} for i in range(800)]
    rows.append({'公司代號':'2308','公司名稱':'台達電子工業股份有限公司','公司簡稱':'台達電','營利事業統一編號':'34051920','出表日期':'1151105','英文簡稱':'DELTA','網址':'https://www.deltaww.com/zh-TW/index'})
    return json.dumps(rows,ensure_ascii=False).encode()
def context():
    return {'ticker':'2308.TW','quote_type':'EQUITY','company_name':'台達電','company_identity':{'ticker':'2308.TW','instrument_type':'EQUITY','official_name':'台達電','legal_name':'台達電子工業股份有限公司','official_ubn':'34051920'}}
