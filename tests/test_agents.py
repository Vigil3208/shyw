from wenan_backend.agents import _parse_json_response
from wenan_backend.schemas import ExtractedFacts


def test_custom_provider_json_response_accepts_code_fence() -> None:
    result = _parse_json_response(ExtractedFacts, "```json\n{\"facts\": []}\n```")
    assert result.facts == []


def test_custom_provider_json_response_repairs_minor_syntax_errors() -> None:
    result = _parse_json_response(ExtractedFacts, "结果如下：{facts: [],}")
    assert result.facts == []
