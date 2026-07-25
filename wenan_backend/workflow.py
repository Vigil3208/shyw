from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .agents import AgentRuntime
from .schemas import (
    Fact,
    Platform,
    PlatformValidation,
    ValidationStatus,
    ValidationSummary,
)
from .validation import FactValidator


class WorkflowState(TypedDict, total=False):
    session_id: str
    original_text: str
    user_instruction: str | None
    facts: list[dict[str, Any]]
    fact_extraction_failed: bool
    xiaohongshu: dict[str, Any] | None
    video: dict[str, Any] | None
    moments: dict[str, Any] | None
    validation: dict[str, Any]
    errors: Annotated[list[dict[str, Any]], operator.add]


class ContentWorkflow:
    def __init__(self, agents: AgentRuntime, validator: FactValidator, checkpointer: Any) -> None:
        self.agents = agents
        self.validator = validator
        builder = StateGraph(WorkflowState)
        builder.add_node("fact_extractor", self._extract_facts)
        builder.add_node("xiaohongshu_agent", self._xiaohongshu)
        builder.add_node("video_agent", self._video)
        builder.add_node("moments_agent", self._moments)
        builder.add_node("fact_validator", self._validate)
        builder.add_edge(START, "fact_extractor")
        builder.add_edge("fact_extractor", "xiaohongshu_agent")
        builder.add_edge("fact_extractor", "video_agent")
        builder.add_edge("fact_extractor", "moments_agent")
        builder.add_edge("xiaohongshu_agent", "fact_validator")
        builder.add_edge("video_agent", "fact_validator")
        builder.add_edge("moments_agent", "fact_validator")
        builder.add_edge("fact_validator", END)
        self.graph = builder.compile(checkpointer=checkpointer)

    @staticmethod
    def _facts(state: WorkflowState) -> list[Fact]:
        return [Fact.model_validate(item) for item in state.get("facts", [])]

    @staticmethod
    def _error(component: str, exc: Exception) -> dict[str, Any]:
        return {
            "component": component,
            "error_type": type(exc).__name__,
            "message": str(exc)[:500],
        }

    def _extract_facts(self, state: WorkflowState) -> dict[str, Any]:
        try:
            facts = self.agents.extract_facts(state["original_text"])
            return {
                "facts": [fact.model_dump(mode="json") for fact in facts],
                "fact_extraction_failed": False,
            }
        except Exception as exc:
            if self.agents.mode == "openai":
                facts = self.agents.extract_facts_fallback(state["original_text"])
                error = self._error("fact_extractor", exc)
                error.update({"recovered": True, "fallback": "local-deterministic-v1"})
                return {
                    "facts": [fact.model_dump(mode="json") for fact in facts],
                    "fact_extraction_failed": False,
                    "errors": [error],
                }
            return {
                "facts": [],
                "fact_extraction_failed": True,
                "errors": [self._error("fact_extractor", exc)],
            }

    def _generate(self, state: WorkflowState, platform: Platform) -> dict[str, Any]:
        key = platform.value
        try:
            content = self.agents.generate(
                platform,
                state["original_text"],
                self._facts(state),
                state.get("user_instruction"),
            )
            return {key: content}
        except Exception as exc:
            if self.agents.mode == "openai":
                fallback = self.agents.generate_fallback(
                    platform,
                    state["original_text"],
                    self._facts(state),
                )
                error = self._error(f"{key}_agent", exc)
                error.update({"recovered": True, "fallback": "local-deterministic-v1"})
                return {key: fallback, "errors": [error]}
            return {key: None, "errors": [self._error(f"{key}_agent", exc)]}

    def _xiaohongshu(self, state: WorkflowState) -> dict[str, Any]:
        return self._generate(state, Platform.XIAOHONGSHU)

    def _video(self, state: WorkflowState) -> dict[str, Any]:
        return self._generate(state, Platform.VIDEO)

    def _moments(self, state: WorkflowState) -> dict[str, Any]:
        return self._generate(state, Platform.MOMENTS)

    def _validate(self, state: WorkflowState) -> dict[str, Any]:
        facts = self._facts(state)
        outputs = {
            Platform.XIAOHONGSHU: state.get("xiaohongshu"),
            Platform.VIDEO: state.get("video"),
            Platform.MOMENTS: state.get("moments"),
        }
        summary = self.validator.validate_all(state["original_text"], facts, outputs)
        recovered_errors: list[dict[str, Any]] = []
        recovered_outputs: dict[str, Any] = {}
        if self.agents.mode == "openai" and not state.get("fact_extraction_failed"):
            for platform in Platform:
                result = summary.platforms[platform.value]
                if result.status != ValidationStatus.FAILED:
                    continue
                fallback = self.agents.generate_fallback(
                    platform,
                    state["original_text"],
                    facts,
                )
                outputs[platform] = fallback
                recovered_outputs[platform.value] = fallback
                recovered_errors.append(
                    {
                        "component": f"{platform.value}_validator",
                        "error_type": "ValidationFailed",
                        "message": "；".join(result.issues)[:500],
                        "recovered": True,
                        "fallback": "local-deterministic-v1",
                    }
                )
            if recovered_outputs:
                summary = self.validator.validate_all(state["original_text"], facts, outputs)
        if state.get("fact_extraction_failed"):
            platforms = {
                platform.value: PlatformValidation(
                    platform=platform,
                    status=ValidationStatus.NOT_COMPLETED,
                    direct_usable=False,
                    fact_coverage=0,
                    issues=["事实抽取失败，不能完成事实一致性校验"],
                )
                for platform in Platform
            }
            summary = ValidationSummary(
                status=ValidationStatus.NOT_COMPLETED,
                direct_usable=False,
                platforms=platforms,
            )
        return {
            "validation": summary.model_dump(mode="json"),
            **recovered_outputs,
            **({"errors": recovered_errors} if recovered_errors else {}),
        }

    def invoke(
        self,
        session_id: str,
        original_text: str,
        user_instruction: str | None,
    ) -> WorkflowState:
        config = {
            "configurable": {"thread_id": session_id},
            "max_concurrency": 3,
            "recursion_limit": 10,
        }
        return self.graph.invoke(
            {
                "session_id": session_id,
                "original_text": original_text,
                "user_instruction": user_instruction,
                "facts": [],
                "errors": [],
            },
            config,
        )
