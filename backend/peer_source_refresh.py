"""Dispatch only explicitly supported peer-source contracts."""


def validate_peer_refresh_context(data,ticker):
 if ticker=='2633.TW':
  from railway_peer_source_refresh import validate_context
  validate_context(data,ticker)
  return 'railway'
 from data_fetch.market_sources.ncc_mobile_peer_cohort import IDENTITIES
 if ticker in IDENTITIES:
  from ncc_peer_source_refresh import validate_ncc_refresh_context
  validate_ncc_refresh_context(data,ticker)
  return 'ncc'
 if ticker=='6192.TW':
  from ic_distribution_peer_source_refresh import validate_context
  validate_context(data,ticker)
  return 'ic_distribution'
 from thermal_peer_source_refresh import validate_thermal_refresh_context
 validate_thermal_refresh_context(data,ticker)
 return 'thermal'


def guard_peer_result(result,data,ticker):
 from data_fetch.market_sources.ncc_mobile_peer_cohort import IDENTITIES
 if ticker in IDENTITIES:
  from ncc_peer_source_refresh import guard_ncc_result
  return guard_ncc_result(result,data,ticker)
 return result


def merge_peer_source(old_data,old_audits,value,audits,ticker):
 policy=validate_peer_refresh_context(old_data,ticker)
 if policy=='ncc':
  from ncc_peer_source_refresh import merge_ncc_peer_source
  return merge_ncc_peer_source(old_data,old_audits,value,audits,ticker)
 if policy=='ic_distribution':
  from ic_distribution_peer_source_refresh import merge_source
  return merge_source(old_data,old_audits,value,audits,ticker)
 if policy=='railway':
  from railway_peer_source_refresh import merge_source
  return merge_source(old_data,old_audits,value,audits,ticker)
 from thermal_peer_source_refresh import merge_thermal_peer_source
 return merge_thermal_peer_source(old_data,old_audits,value,audits,ticker)
