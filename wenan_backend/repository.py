from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from .schemas import (
    Fact,
    OutputView,
    Platform,
    PlatformValidation,
    SessionListItem,
    SessionStatus,
    SessionView,
    ValidationStatus,
    ValidationSummary,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Repository:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=15)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 15000")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    status TEXT NOT NULL,
                    user_instruction TEXT,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    validation_json TEXT,
                    errors_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE TABLE IF NOT EXISTS facts (
                    fact_id TEXT NOT NULL,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    type TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    normalized_value TEXT NOT NULL,
                    source_start INTEGER NOT NULL,
                    source_end INTEGER NOT NULL,
                    criticality TEXT NOT NULL,
                    review_status TEXT NOT NULL,
                    PRIMARY KEY (session_id, fact_id)
                );

                CREATE TABLE IF NOT EXISTS outputs (
                    output_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    platform TEXT NOT NULL,
                    content_json TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    validation_status TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE (session_id, platform, version)
                );

                CREATE TABLE IF NOT EXISTS generation_runs (
                    run_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
                    platform TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    errors_json TEXT NOT NULL DEFAULT '[]'
                );

                CREATE INDEX IF NOT EXISTS idx_outputs_latest
                    ON outputs(session_id, platform, version DESC);
                CREATE INDEX IF NOT EXISTS idx_sessions_updated
                    ON sessions(updated_at DESC);
                """
            )

    def create_session(
        self,
        session_id: str,
        original_text: str,
        user_instruction: str | None,
        model_name: str,
        prompt_version: str,
    ) -> None:
        now = _now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    session_id, created_at, updated_at, original_text, status,
                    user_instruction, model_name, prompt_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    now,
                    now,
                    original_text,
                    SessionStatus.PROCESSING.value,
                    user_instruction,
                    model_name,
                    prompt_version,
                ),
            )

    def start_run(
        self,
        session_id: str,
        model_name: str,
        prompt_version: str,
        platform: Platform | None = None,
    ) -> str:
        run_id = str(uuid.uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO generation_runs (
                    run_id, session_id, platform, started_at, status, model_name, prompt_version
                ) VALUES (?, ?, ?, ?, 'processing', ?, ?)
                """,
                (
                    run_id,
                    session_id,
                    platform.value if platform else None,
                    _now(),
                    model_name,
                    prompt_version,
                ),
            )
        return run_id

    def _finish_run(
        self, connection: sqlite3.Connection, run_id: str, status: str, errors: list[dict[str, Any]]
    ) -> None:
        connection.execute(
            """
            UPDATE generation_runs
            SET completed_at = ?, status = ?, errors_json = ?
            WHERE run_id = ?
            """,
            (_now(), status, _json(errors), run_id),
        )

    @staticmethod
    def _insert_output(
        connection: sqlite3.Connection,
        session_id: str,
        platform: Platform,
        content: dict[str, Any],
        validation: PlatformValidation,
    ) -> None:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 AS version FROM outputs WHERE session_id = ? AND platform = ?",
            (session_id, platform.value),
        ).fetchone()
        version = int(row["version"])
        connection.execute(
            """
            INSERT INTO outputs (
                output_id, session_id, platform, content_json, version,
                validation_status, validation_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                session_id,
                platform.value,
                _json(content),
                version,
                validation.status.value,
                _json(validation),
                _now(),
            ),
        )

    def complete_generation(
        self,
        session_id: str,
        run_id: str,
        facts: Iterable[Fact],
        outputs: dict[Platform, dict[str, Any] | None],
        validation: ValidationSummary,
        errors: list[dict[str, Any]],
    ) -> None:
        successful = sum(value is not None for value in outputs.values())
        status = (
            SessionStatus.SUCCESS
            if successful == len(Platform)
            else SessionStatus.PARTIAL_FAILURE
            if successful
            else SessionStatus.FAILED
        )
        now = _now()
        with self._connect() as connection:
            connection.execute("DELETE FROM facts WHERE session_id = ?", (session_id,))
            for fact in facts:
                connection.execute(
                    """
                    INSERT INTO facts (
                        fact_id, session_id, type, source_text, normalized_value,
                        source_start, source_end, criticality, review_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact.fact_id,
                        session_id,
                        fact.type.value,
                        fact.source_text,
                        fact.normalized_value,
                        fact.source_start,
                        fact.source_end,
                        fact.criticality.value,
                        fact.review_status.value,
                    ),
                )
            for platform, content in outputs.items():
                if content is not None:
                    self._insert_output(
                        connection,
                        session_id,
                        platform,
                        content,
                        validation.platforms[platform.value],
                    )
            connection.execute(
                """
                UPDATE sessions
                SET updated_at = ?, status = ?, validation_json = ?, errors_json = ?
                WHERE session_id = ?
                """,
                (now, status.value, _json(validation), _json(errors), session_id),
            )
            self._finish_run(connection, run_id, status.value, errors)

    def complete_regeneration(
        self,
        session_id: str,
        run_id: str,
        platform: Platform,
        content: dict[str, Any],
        platform_validation: PlatformValidation,
        overall_validation: ValidationSummary,
        instruction: str | None,
    ) -> None:
        with self._connect() as connection:
            self._insert_output(connection, session_id, platform, content, platform_validation)
            connection.execute(
                """
                UPDATE sessions
                SET updated_at = ?, status = ?, user_instruction = ?, validation_json = ?, errors_json = '[]'
                WHERE session_id = ?
                """,
                (
                    _now(),
                    SessionStatus.SUCCESS.value,
                    instruction,
                    _json(overall_validation),
                    session_id,
                ),
            )
            self._finish_run(connection, run_id, SessionStatus.SUCCESS.value, [])

    def mark_failed(
        self,
        session_id: str,
        run_id: str,
        error: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET updated_at = ?, status = ?, errors_json = ? WHERE session_id = ?",
                (_now(), SessionStatus.FAILED.value, _json([error]), session_id),
            )
            self._finish_run(connection, run_id, SessionStatus.FAILED.value, [error])

    def fail_regeneration(
        self,
        session_id: str,
        run_id: str,
        error: dict[str, Any],
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE sessions SET updated_at = ?, status = ?, errors_json = ? WHERE session_id = ?",
                (_now(), SessionStatus.PARTIAL_FAILURE.value, _json([error]), session_id),
            )
            self._finish_run(connection, run_id, SessionStatus.FAILED.value, [error])

    def get_session(self, session_id: str) -> SessionView | None:
        with self._connect() as connection:
            session = connection.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if session is None:
                return None
            facts = [
                Fact.model_validate(dict(row))
                for row in connection.execute(
                    """
                    SELECT fact_id, type, source_text, normalized_value, source_start,
                           source_end, criticality, review_status
                    FROM facts WHERE session_id = ? ORDER BY source_start, fact_id
                    """,
                    (session_id,),
                ).fetchall()
            ]
            output_rows = connection.execute(
                """
                SELECT * FROM (
                    SELECT outputs.*,
                           ROW_NUMBER() OVER (PARTITION BY platform ORDER BY version DESC) AS row_num
                    FROM outputs WHERE session_id = ?
                ) WHERE row_num = 1
                """,
                (session_id,),
            ).fetchall()

        outputs: dict[str, OutputView] = {}
        for row in output_rows:
            platform = Platform(row["platform"])
            outputs[platform.value] = OutputView(
                output_id=row["output_id"],
                platform=platform,
                content=json.loads(row["content_json"]),
                version=row["version"],
                validation_status=ValidationStatus(row["validation_status"]),
                validation_detail=PlatformValidation.model_validate(json.loads(row["validation_json"])),
                created_at=row["created_at"],
            )
        return SessionView(
            session_id=session["session_id"],
            created_at=session["created_at"],
            updated_at=session["updated_at"],
            original_text=session["original_text"],
            status=SessionStatus(session["status"]),
            user_instruction=session["user_instruction"],
            model_name=session["model_name"],
            prompt_version=session["prompt_version"],
            facts=facts,
            outputs=outputs,
            validation=ValidationSummary.model_validate(json.loads(session["validation_json"]))
            if session["validation_json"]
            else None,
            errors=json.loads(session["errors_json"]),
        )

    def list_sessions(self, limit: int = 20, offset: int = 0) -> list[SessionListItem]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT session_id, created_at, updated_at, status, original_text
                FROM sessions ORDER BY updated_at DESC LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [
            SessionListItem(
                session_id=row["session_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                status=SessionStatus(row["status"]),
                original_text_preview=row["original_text"][:100],
            )
            for row in rows
        ]
