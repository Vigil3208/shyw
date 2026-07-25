from wenan_backend.facts import extract_facts_locally
from wenan_backend.schemas import Platform, ValidationStatus
from wenan_backend.validation import FactValidator


def test_validator_rejects_new_numeric_fact() -> None:
    original = "这座古建筑始建于宋代，占地3000平方米。"
    facts = extract_facts_locally(original)
    content = {
        "titles": ["标题一", "标题二", "标题三", "标题四", "标题五"],
        "body": "〖宋代〗古建筑占地〖3000平方米〗，门票80元。",
        "tags": ["#文旅", "#旅行", "#建筑"],
        "cover_suggestion": "使用真实现场图",
    }

    result = FactValidator().validate_platform(
        Platform.XIAOHONGSHU, content, original, facts
    )

    assert result.status == ValidationStatus.FAILED
    assert any("原文外的数字事实" in issue for issue in result.issues)


def test_validator_allows_unused_fact_but_reports_it() -> None:
    original = "景区始建于宋代，占地3000平方米。"
    facts = extract_facts_locally(original)
    content = {
        "titles": ["标题一", "标题二", "标题三", "标题四", "标题五"],
        "body": "只介绍〖宋代〗的故事。",
        "tags": ["#文旅", "#旅行", "#建筑"],
        "cover_suggestion": "使用真实现场图",
    }

    result = FactValidator().validate_platform(
        Platform.XIAOHONGSHU, content, original, facts
    )

    assert result.status == ValidationStatus.PASSED
    assert any(item.status == "not_used" for item in result.details)
