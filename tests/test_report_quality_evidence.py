from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def test_artifact_quality_summary_recognizes_chinese_content_credibility_marker():
    from report_quality_evidence import read_artifact_quality_summary

    def load_item(_storage, _filename, *, kind):
        assert kind == "md"
        return SimpleNamespace(content="- **內容一致性:** 有警示\n".encode("utf-8"))

    assert read_artifact_quality_summary(object(), "report.md", load_item=load_item) == {
        "status": "present",
        "source": "markdown",
        "fields": ["content_credibility"],
    }
