from wenan_backend.facts import detect_sensitive_information, extract_facts_locally
from wenan_backend.schemas import FactType


def test_local_fact_extractor_tracks_source_positions() -> None:
    text = "景区位于苏州市，始建于宋代，占地3000平方米，门票50元，开放时间08:00-17:00。"

    facts = extract_facts_locally(text)

    types = {fact.type for fact in facts}
    assert FactType.ERA in types
    assert FactType.AREA in types
    assert FactType.PRICE in types
    assert FactType.OPENING_HOURS in types
    assert [fact.fact_id for fact in facts] == [f"F{i:03d}" for i in range(1, len(facts) + 1)]
    for fact in facts:
        assert text[fact.source_start : fact.source_end] == fact.source_text


def test_sensitive_information_is_detected_without_returning_value() -> None:
    detected = detect_sensitive_information("联系人手机号 13800138000，邮箱 a@example.com")
    assert detected == ["中国大陆手机号", "电子邮箱"]
