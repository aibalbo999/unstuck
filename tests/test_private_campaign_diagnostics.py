import pytest
from quality_campaign_graph import diagnostic_event_projection


def test_projection_is_cutoff_bound_deduplicated_and_not_a_quality_rate():
    jobs=[{'job_id':'fixture','status':'done','pipeline_id':'v4'}]
    def event(i,phase,**fields):
        return {'id':i,'job_id':'fixture','created_at':10,'payload':{'phase':phase,**fields}}
    rows=[event(1,'llm_provider_request'),event(2,'llm_model_error',type='error',metadata={'provider_status_code':429}),
          event(3,'llm_model_error',type='error',metadata={'error_kind':'ProviderCongestionError'}),
          event(4,'report_quality_blocked',type='error'),event(5,'fixture_other_error',type='error')]
    rows += [rows[0],{**rows[0],'id':6,'created_at':11},{'id':7,'job_id':'fixture','created_at':float('nan'),'payload':{}}]
    result=diagnostic_event_projection(jobs,rows,cutoff=10)
    assert result['event_counts']=={'provider_request_events':1,'provider_quota_error_events':1,
        'local_block_events':1,'other_error_events':1,'quality_rejection_events':1,'publication_events':0}
    assert result['scope']['events_selected']==5 and result['scope']['duplicate_events_excluded']==1
    assert result['scope']['future_events_excluded']==1 and result['scope']['events_malformed']==1
    assert result['qualified_for_campaign'] is result['formal_publication'] is False
    assert result['qualified_success_rate'] is None


@pytest.mark.parametrize('cutoff',[True,float('inf'),float('nan'),'10'])
def test_invalid_cutoff_is_rejected(cutoff):
    with pytest.raises(ValueError):diagnostic_event_projection([],[],cutoff=cutoff)
