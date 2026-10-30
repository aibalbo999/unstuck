"""Dispatch only explicitly supported peer-source contracts."""


def validate_peer_refresh_context(data,ticker):
 from data_fetch.market_sources.ncc_mobile_peer_cohort import IDENTITIES
 if ticker in IDENTITIES:
  from ncc_peer_source_refresh import validate_ncc_refresh_context
  validate_ncc_refresh_context(data,ticker)
  return 'ncc'
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
 if validate_peer_refresh_context(old_data,ticker)=='ncc':
  from ncc_peer_source_refresh import merge_ncc_peer_source
  return merge_ncc_peer_source(old_data,old_audits,value,audits,ticker)
 from thermal_peer_source_refresh import merge_thermal_peer_source
 return merge_thermal_peer_source(old_data,old_audits,value,audits,ticker)
