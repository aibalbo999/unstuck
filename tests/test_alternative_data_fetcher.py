import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, text):
        self.text = text
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.text)


def test_fetch_104_job_openings_count_extracts_total_from_html():
    from alternative_data_fetcher import fetch_104_job_openings_count

    session = FakeSession(
        """
        <html>
          <body>
            <script>window.__STATE__={"totalCount":128,"other":true}</script>
            <h1>台達電 散熱 職缺</h1>
          </body>
        </html>
        """
    )

    result = fetch_104_job_openings_count("台達電", "散熱", session=session)

    assert result["job_count"] == 128
    assert result["company_name"] == "台達電"
    assert result["keyword"] == "散熱"
    assert "104.com.tw" in result["source_url"]
    headers = session.calls[0][1]["headers"]
    assert "Mozilla" in headers["User-Agent"]


def test_fetch_104_job_openings_count_falls_back_to_text_pattern():
    from alternative_data_fetcher import fetch_104_job_openings_count

    session = FakeSession("<main>搜尋結果：共 36 筆工作機會</main>")

    result = fetch_104_job_openings_count("台達電", "液冷", session=session)

    assert result["job_count"] == 36


def test_fetch_104_job_openings_count_returns_unavailable_on_parse_failure():
    from alternative_data_fetcher import fetch_104_job_openings_count

    result = fetch_104_job_openings_count("台達電", "AI", session=FakeSession("<html></html>"))

    assert result["status"] == "unavailable"
    assert result["job_count"] is None
