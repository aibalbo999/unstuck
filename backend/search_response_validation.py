"""Validate search response shapes before an empty result can mean no matches."""
from __future__ import annotations

from xml.etree import ElementTree

from search_provider_runtime import SourceResponseError, observe_http_response


async def observed_json_get(client, url, params, headers=None):
    response = await client.get(url, params=params, headers=headers)
    observe_http_response(response)
    response.raise_for_status()
    return response_json(response)


def response_json(response):
    try:
        return response.json()
    except ValueError as exc:
        raise SourceResponseError("parse_error", status_code=getattr(response, "status_code", None), response_text=response.text, parser_version="search-json-v1") from exc


def validate_payload(payload, required, *, allow_empty=None):
    if not isinstance(payload, dict):
        raise SourceResponseError("parse_error")
    if payload.get("error") or payload.get("errors"):
        raise SourceResponseError("provider_error")
    if required not in payload and not (allow_empty and allow_empty in payload):
        raise SourceResponseError("parse_error")


def validate_rss(text):
    try:
        root = ElementTree.fromstring(text)
    except ElementTree.ParseError as exc:
        raise SourceResponseError("parse_error", response_text=text, parser_version="rss-v1") from exc
    if root.tag.lower() != "rss" or root.find("channel") is None:
        raise SourceResponseError("parse_error", response_text=text, parser_version="rss-v1")
