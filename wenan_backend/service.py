from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from .agents import AgentRuntime
from .config import Settings
from .facts import detect_sensitive_information
from .repository import Repository
from .schemas import (
    Fact,
    GenerateRequest,
    Platform,
    SessionListItem,
    SessionView,
    ValidationSummary,
)
from .validation import FactValidator
from .workflow import ContentWorkflow


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _error(component: str, exc: Exception) -> dict[str, Any]:
    return {
        "component": component,
        "error_type": type(exc).__name__,
        "message": str(exc)[:500],
    }


class ContentService:
    def __init__(self, settings: Settings) -> None:
        settings.validate()
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.settings = settings
        self.repository = Repository(settings.database_path)
        self.repository.initialize()
        self.agents = AgentRuntime(settings)
        self.validator = FactValidator()
        self._checkpoint_connection = sqlite3.connect(
            settings.checkpoint_path,
            check_same_thread=False,
            timeout=15,
        )
        self._checkpoint_connection.execute("PRAGMA journal_mode = WAL")
        self.checkpointer = SqliteSaver(self._checkpoint_connection)
        self.checkpointer.setup()
        self.workflow = ContentWorkflow(self.agents, self.validator, self.checkpointer)

    @property
    def model_label(self) -> str:
        return self.agents.model_label

    def close(self) -> None:
        self._checkpoint_connection.close()

    def _validate_input(self, text: str) -> None:
        if len(text) > self.settings.max_input_chars:
            raise ServiceError(
                "input_too_long",
                f"讲解词不能超过 {self.settings.max_input_chars} 个字符",
                422,
            )
        sensitive = detect_sensitive_information(text)
        if sensitive:
            raise ServiceError(
                "sensitive_information_detected",
                "输入中疑似包含" + "、".join(sensitive) + "，请删除或脱敏后重试",
                422,
            )

    def generate(self, request: GenerateRequest) -> SessionView:
        self._validate_input(request.original_text)
        session_id = str(uuid.uuid4())
        self.repository.create_session(
            session_id,
            request.original_text,
            request.user_instruction,
            self.model_label,
            self.settings.prompt_version,
        )
        run_id = self.repository.start_run(
            session_id, self.model_label, self.settings.prompt_version
        )
        try:
            result = self.workflow.invoke(
                session_id,
                request.original_text,
                request.user_instruction,
            )
            facts = [Fact.model_validate(item) for item in result.get("facts", [])]
            outputs = {
                Platform.XIAOHONGSHU: result.get("xiaohongshu"),
                Platform.VIDEO: result.get("video"),
                Platform.MOMENTS: result.get("moments"),
            }
            validation = ValidationSummary.model_validate(result["validation"])
            errors = result.get("errors", [])
            self.repository.complete_generation(
                session_id,
                run_id,
                facts,
                outputs,
                validation,
                errors,
            )
        except Exception as exc:
            self.repository.mark_failed(session_id, run_id, _error("workflow", exc))
            raise ServiceError(
                "generation_failed",
                f"内容生成失败，会话 {session_id} 已保留，可查看错误详情",
                500,
            ) from exc
        session = self.repository.get_session(session_id)
        if session is None:
            raise RuntimeError("会话写入后无法读取")
        return session

    def get_session(self, session_id: str) -> SessionView:
        session = self.repository.get_session(session_id)
        if session is None:
            raise ServiceError("session_not_found", "会话不存在", 404)
        return session

    def list_sessions(self, limit: int, offset: int) -> list[SessionListItem]:
        return self.repository.list_sessions(limit, offset)

    def regenerate(
        self,
        session_id: str,
        platform: Platform,
        instruction: str | None,
    ) -> SessionView:
        current = self.get_session(session_id)
        run_id = self.repository.start_run(
            session_id,
            self.model_label,
            self.settings.prompt_version,
            platform,
        )
        try:
            content = self.agents.generate(
                platform,
                current.original_text,
                current.facts,
                instruction,
                current.outputs[platform.value].content
                if platform.value in current.outputs
                else None,
            )
            latest_outputs = {
                item: current.outputs[item.value].content if item.value in current.outputs else None
                for item in Platform
            }
            latest_outputs[platform] = content
            overall = self.validator.validate_all(
                current.original_text,
                current.facts,
                latest_outputs,
            )
            platform_validation = overall.platforms[platform.value]
            self.repository.complete_regeneration(
                session_id,
                run_id,
                platform,
                content,
                platform_validation,
                overall,
                instruction,
            )
        except Exception as exc:
            self.repository.fail_regeneration(session_id, run_id, _error(f"{platform.value}_agent", exc))
            raise ServiceError(
                "regeneration_failed",
                "单平台重新生成失败，已有结果未被覆盖",
                500,
            ) from exc
        return self.get_session(session_id)
