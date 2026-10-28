"""The settings panel must describe the summary routes actually executed."""

def test_summary_snapshot_reports_actual_backup_sequence_and_changes_its_digest(monkeypatch):
    import tear_sheet_tasks as tasks
    from agent_effective_settings import build_agent_settings_payload
    monkeypatch.setattr(tasks,'_tear_sheet_model_sequence',lambda:['gemini-primary'])
    before=build_agent_settings_payload()
    monkeypatch.setattr(tasks,'_tear_sheet_model_sequence',lambda:['gemini-primary','gemini-backup'])
    after=build_agent_settings_payload()
    assert after['auxiliary_roles']['tear_sheet']['model_sequence']==['gemini-primary','gemini-backup']
    assert after['effective_settings_sha256']!=before['effective_settings_sha256']
    assert after['local_model_limits']==before['local_model_limits']
    assert after['agents']==before['agents']
