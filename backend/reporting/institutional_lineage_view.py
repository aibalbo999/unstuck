"""Present the exact recomputation boundary of cited institutional flows."""
from html import escape


def rows(context):
    gate=context.get('content_credibility') or {}
    for check in gate.get('checks',[]) if isinstance(gate,dict) else []:
        if check.get('id')=='v4_institutional_claim_lineage':
            return list((check.get('details') or {}).get('references',{}).items())
    return []


def parts(ref,r):
    dates=r.get('observation_dates') or []
    values = [('引用',ref),('核對結果',{'recomputed':'保存逐日資料可重算','mismatch':'彙總與逐日資料矛盾','unavailable':'缺少完整逐日證據'}.get(r['status'],r['status'])),
            ('統計主體／單位',str(r.get('population'))+' / '+str(r.get('unit'))),
            ('觀測日期窗',f'{dates[0]} 至 {dates[-1]}，{len(dates)} 個已核對交易日' if dates else '未知'),
            ('逐日股數加總',str(r.get('recomputed_shares','未知'))),('主張值／重算值',str(r.get('reported_value'))+' / '+str(r.get('recomputed_value','未知'))),
            ('資料取得時間',str(r.get('provider_acquired_at') or '未保存')),
            ('保存資料位置',str(r.get('normalized_observations_path') or '未保存')),
            ('保存分項 SHA256',str(r.get('normalized_observations_sha256') or '未保存')),
            ('判準',r['reason']),('官方逐日核對',str((r.get('official_comparison') or {}).get('matched_count',0))+' 日一致'),('獨立官方來源與歷史時點驗證', '官方逐日數值一致；歷史PIT與上漲因果未驗證' if r.get('independent_primary_source_verified') else '尚未成立；可重算不代表投資結論或上漲有效')]

    for day in (r.get('official_comparison') or {}).get('comparisons',[]):
        values.append(('官方 '+day['date'], str(day.get('status'))+'；官方 '+str(day.get('official_shares'))+' 股；差 '+str(day.get('delta_shares'))+' 股；取得 '+str(day.get('retrieved_at'))+'；'+str(day.get('source_url'))+'；原始HTTP SHA256 '+str(day.get('raw_response_sha256'))))
    return values


def lineage_markdown(context):
    records=rows(context)
    if not records:return ''
    lines=['\n<!-- evidence-ledger:start -->','\n### 法人方向理由來源鏈']
    for ref,r in records:
        lines += [f'- **{label}:** {value}' for label,value in parts(ref,r)]
    return '\n'.join(lines+['<!-- evidence-ledger:end -->'])


def lineage_html(context):
    records=rows(context)
    if not records:return ''
    return '<details class="institutional-lineage"><summary>法人方向理由來源鏈</summary>' + ''.join('<dl>'+''.join('<dt>'+escape(label)+'</dt><dd style="overflow-wrap:anywhere">'+escape(value)+'</dd>' for label,value in parts(ref,r))+'</dl>' for ref,r in records)+'</details>'
