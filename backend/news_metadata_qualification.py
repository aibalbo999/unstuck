"""Qualify metadata-only news without manufacturing an event or article body."""


def qualify_headline_metadata(record):
    if not isinstance(record, dict):
        return record
    result = dict(record)
    provider = result.get('source')
    if provider not in {'GDELT', 'Google News RSS'}:
        return result
    result.update(
        evidence_coverage='headline_metadata_only',
        article_body_verified=False,
        published_at_basis=('rss_pubDate' if provider == 'Google News RSS'
                            else 'gdelt_seen_or_provider_date'),
        event_date=None,
        event_date_verified=False,
        event_date_basis='not_established_by_news_metadata',
    )
    return result
