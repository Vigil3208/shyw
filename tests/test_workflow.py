from langgraph.checkpoint.memory import InMemorySaver

from wenan_backend.agents import AgentRuntime
from wenan_backend.config import Settings
from wenan_backend.schemas import Platform, ValidationStatus
from wenan_backend.validation import FactValidator
from wenan_backend.workflow import ContentWorkflow


class _ModelWithInvalidMoments:
    mode = "openai"

    def __init__(self) -> None:
        self.local = AgentRuntime(Settings(model_mode="local"))

    def extract_facts(self, original_text):
        return self.local.extract_facts(original_text)

    def extract_facts_fallback(self, original_text):
        return self.local.extract_facts_fallback(original_text)

    def generate(self, platform, original_text, facts, user_instruction=None):
        content = self.local.generate_fallback(platform, original_text, facts)
        if platform == Platform.MOMENTS:
            content["pinned_tips"]["交通"] = "步行3小时"
        return content

    def generate_fallback(self, platform, original_text, facts):
        return self.local.generate_fallback(platform, original_text, facts)


def test_validation_failure_is_recovered_per_platform() -> None:
    workflow = ContentWorkflow(
        _ModelWithInvalidMoments(),
        FactValidator(),
        InMemorySaver(),
    )

    result = workflow.invoke(
        "test-recovery",
        "拙政园位于苏州市，始建于明代，占地78亩。",
        None,
    )

    assert result["validation"]["status"] == ValidationStatus.PASSED.value
    assert result["validation"]["direct_usable"] is True
    assert result["moments"]["pinned_tips"]["交通"] == "待补充"
    assert any(
        error.get("component") == "moments_validator" and error.get("recovered") is True
        for error in result["errors"]
    )
