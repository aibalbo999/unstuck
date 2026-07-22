from types import MappingProxyType


def test_news_record_utils_builds_canonical_records_and_dedupes_links():
    from news_record_utils import dedupe_records, news_record

    first = news_record(
        title=" <b>TSMC expands</b> ",
        link="/story?utm_source=rss&keep=1&fbclid=secret",
        published_date="2026-06-19T08:00:00Z",
        source="<span>Example Wire</span>",
        summary="<p>Capacity update</p>",
        base_url="https://News.Example/root/",
    )
    duplicate = news_record(
        title="Duplicate",
        link="https://news.example/story?keep=1&utm_campaign=x",
        published_date=(2026, 6, 19, 8, 0, 0, 4, 170, 0),
        source="Other Wire",
        summary="Duplicate item",
    )
    invalid = news_record(
        title="Invalid",
        link="javascript:alert(1)",
        published_date="not a date",
        source="Bad",
        summary="Bad",
    )

    assert first == {
        "title": "TSMC expands",
        "link": "https://news.example/story?keep=1",
        "published_date": "2026-06-19T08:00:00+00:00",
        "source": "Example Wire",
        "summary": "Capacity update",
    }
    assert invalid is None
    assert dedupe_records([first, duplicate], limit=5) == [first]


def test_news_record_utils_cleans_input_and_clamps_limits():
    from news_record_utils import MAX_INPUT_LENGTH, clean_input, clamp_limit

    assert clean_input("  台積電\n2330\t新聞  ") == "台積電 2330 新聞"
    assert len(clean_input("x" * (MAX_INPUT_LENGTH + 5))) == MAX_INPUT_LENGTH
    assert clamp_limit("bad") == 10
    assert clamp_limit(0) == 1
    assert clamp_limit(999) == 50


def test_news_record_utils_accepts_mapping_proxy_records():
    from news_record_utils import dedupe_records

    records = [
        MappingProxyType(
            {
                "title": "Title",
                "link": "https://example.com/a",
                "published_date": "",
                "source": "",
                "summary": "",
            }
        )
    ]

    assert dedupe_records(records, limit=1) == [records[0]]
