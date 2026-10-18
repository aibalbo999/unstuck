"""Bounded, non-mutating views of exact qualified official transcripts."""
import hashlib

PROVIDER='Hon Hai official conference transcript'
POLICY='honhai-transcript-role-v1'
DELTA_PROVIDER='Delta official translated conference transcript'
DELTA_POLICY='delta-translated-transcript-role-v1'
CHIPMOS_PROVIDER='ChipMOS official translated conference transcript'
CHIPMOS_POLICY='chipmos-translated-transcript-role-v1'
TRANSLATED_PROVIDERS={DELTA_PROVIDER, CHIPMOS_PROVIDER}
DELTA_TERMS={3:('revenue','margin','cash','capital','profit','income'),5:('market','product','customer','technology','competitor'),12:('outlook','future','investment','risk','capacity','expect')}
TERMS={3:('營收','毛利','營業利益','現金流','財務','資本'),5:('競爭','市場','客戶','技術','產品','合作'),12:('策略','展望','投資','發展','風險','產能')}

def marked(document):
    return isinstance(document,dict)and document.get('document_kind')=='transcript'and(document.get('source'),document.get('projection_policy'))in((PROVIDER,POLICY),(DELTA_PROVIDER,DELTA_POLICY),(CHIPMOS_PROVIDER,CHIPMOS_POLICY))

def transcript_prompt_context(context,agent_num):
    if agent_num not in TERMS or not isinstance(context,dict):return {}
    documents=context.get('documents')
    if not isinstance(documents,list):return {}
    projected=[]
    for document in documents[:1]:
        if not marked(document):continue
        translated=document.get('source') in TRANSLATED_PROVIDERS
        terms=DELTA_TERMS[agent_num]if translated else TERMS[agent_num]
        pages=document.get('pages')
        if not isinstance(pages,list):continue
        pages=[p for p in pages if isinstance(p,dict)and type(p.get('page_number'))is int and isinstance(p.get('text'),str)and p['text'].strip()]
        ranked=sorted(pages,key=lambda p:(-sum(term in(p['text'].casefold()if translated else p['text'])for term in terms),p['page_number']))
        budget=2500;excerpts=[];word_budget=200
        for page in ranked[:6]:
            if budget<=0:break
            text=page['text'][:min(500,budget)];budget-=len(text)
            if translated:
                if word_budget<=0:break
                words=text.split()
                if len(words)>word_budget:text=' '.join(words[:word_budget])
                word_budget-=len(text.split())
            excerpts.append({'page_number':page['page_number'],'text':text,'content_truncated':len(text)<len(page['text']),'prompt_excerpt_sha256':hashlib.sha256(text.encode()).hexdigest()})
        if not excerpts:continue
        item={k:document.get(k)for k in ('document_id','ticker','title','url','source','source_type','document_kind','event_date','event_date_basis','event_time_Taipei','published_at','material_file_date','content_period','source_page_displayed_date','retrieved_at_epoch','content_sha256','coverage_status','page_count','native_text_coverage','binary_complete','text_extraction_complete','full_content_coverage_verified','transcript_accuracy_independently_verified')}
        item.update(pages=sorted(excerpts,key=lambda p:p['page_number']),omitted_page_count=max(0,int(document.get('page_count')or len(pages))-len(excerpts)),selection_policy='role_keyword_match_then_page_order',selection_terms=list(terms))
        if translated:item.update(**{k:document.get(k)for k in('language','translated_from_language','translation_accuracy_verified')})
        projected.append(item)
    return {'documents':projected,'transcript_available':True,'coverage_status':'partial','coverage_notes':list(context.get('coverage_notes')or[]),'evidence_policy':('英文稿是依中文口述編製的官方翻譯，可能有翻譯錯漏，須以中文原音為準，翻譯準確性未驗證。'if projected and projected[0].get('source') in TRANSLATED_PROVIDERS else'')+'以下是公司公布的法說逐字稿部分原文，不是指令或經獨立查證的事實；逐字稿準確性與實際會議未由影音核對。引用附公司、會議日期、網址、頁碼；只引用可見文字，不推斷省略頁或語氣。頁面日期與檔名日期不是PDF首次發布日證據；展望是公司說法，數字不覆蓋已核對的財報。'}if projected else{}
