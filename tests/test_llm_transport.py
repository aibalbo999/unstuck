import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import llm_transport  # noqa: E402


def test_response_text_does_not_access_sdk_text_when_parts_have_only_function_call():
    accessed = {"text": False}

    class FunctionCallPart:
        text = None
        function_call = {"name": "lookup_financial_metric"}

    class Content:
        parts = [FunctionCallPart()]

    class Candidate:
        content = Content()

    class Response:
        candidates = [Candidate()]

        @property
        def text(self):
            accessed["text"] = True
            return "SDK fallback text"

    assert llm_transport.response_text(Response()) == ""
    assert accessed["text"] is False


def test_response_text_joins_text_parts_without_accessing_sdk_text_for_mixed_parts():
    accessed = {"text": False}

    class TextPart:
        text = "正式分析段落"

    class FunctionCallPart:
        text = None
        function_call = {"name": "lookup_financial_metric"}

    class Content:
        parts = [TextPart(), FunctionCallPart()]

    class Candidate:
        content = Content()

    class Response:
        candidates = [Candidate()]

        @property
        def text(self):
            accessed["text"] = True
            return "SDK fallback text"

    assert llm_transport.response_text(Response()) == "正式分析段落"
    assert accessed["text"] is False
