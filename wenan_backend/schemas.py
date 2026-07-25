from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FactType(StrEnum):
    ERA = "era"
    DATE = "date"
    PERSON = "person"
    PLACE = "place"
    ORGANIZATION = "organization"
    NUMBER = "number"
    AREA = "area"
    PRICE = "price"
    OPENING_HOURS = "opening_hours"
    EVENT = "event"
    OTHER = "other"


class Criticality(StrEnum):
    CRITICAL = "critical"
    GENERAL = "general"


class ReviewStatus(StrEnum):
    CONFIRMED = "confirmed"
    PENDING = "pending"


class Platform(StrEnum):
    XIAOHONGSHU = "xiaohongshu"
    VIDEO = "video"
    MOMENTS = "moments"


class SessionStatus(StrEnum):
    PROCESSING = "processing"
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


class ValidationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"
    NOT_COMPLETED = "not_completed"


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str = ""
    type: FactType
    source_text: str = Field(min_length=1)
    normalized_value: str = Field(min_length=1)
    source_start: int = Field(ge=-1)
    source_end: int = Field(ge=-1)
    criticality: Criticality = Criticality.GENERAL
    review_status: ReviewStatus = ReviewStatus.CONFIRMED


class ExtractedFacts(BaseModel):
    facts: list[Fact] = Field(default_factory=list)


class XiaohongshuContent(BaseModel):
    titles: list[str] = Field(min_length=5, max_length=8)
    body: str = Field(min_length=1)
    tags: list[str] = Field(min_length=3, max_length=5)
    cover_suggestion: str = Field(min_length=1)


class VideoShot(BaseModel):
    time_range: str
    visual: str
    narration: str
    subtitle_keywords: list[str] = Field(default_factory=list)
    pace: str


class VideoContent(BaseModel):
    duration_seconds: int = Field(ge=40, le=60)
    bgm_style: str
    shots: list[VideoShot] = Field(min_length=5)


class GridShot(BaseModel):
    position: int = Field(ge=1, le=9)
    content: str
    composition: str
    color_tone: str
    shot_size: str


class MomentsContent(BaseModel):
    poster_quotes: list[str] = Field(min_length=2, max_length=2)
    body: str = Field(min_length=1)
    grid: list[GridShot] = Field(min_length=9, max_length=9)
    pinned_tips: dict[str, str]


class FactValidationItem(BaseModel):
    fact_id: str
    source_text: str
    occurrence: str | None = None
    status: str
    message: str


class PlatformValidation(BaseModel):
    platform: Platform
    status: ValidationStatus
    direct_usable: bool
    fact_coverage: float = Field(ge=0, le=1)
    details: list[FactValidationItem] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class ValidationSummary(BaseModel):
    status: ValidationStatus
    direct_usable: bool
    platforms: dict[str, PlatformValidation] = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    original_text: str
    user_instruction: str | None = Field(default=None, max_length=1_000)

    @field_validator("original_text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("讲解词不能为空")
        return value


class RegenerateRequest(BaseModel):
    user_instruction: str | None = Field(default=None, max_length=1_000)


class OutputView(BaseModel):
    output_id: str
    platform: Platform
    content: dict[str, Any]
    version: int
    validation_status: ValidationStatus
    validation_detail: PlatformValidation
    created_at: str


class SessionView(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    original_text: str
    status: SessionStatus
    user_instruction: str | None = None
    model_name: str
    prompt_version: str
    facts: list[Fact] = Field(default_factory=list)
    outputs: dict[str, OutputView] = Field(default_factory=dict)
    validation: ValidationSummary | None = None
    errors: list[dict[str, Any]] = Field(default_factory=list)


class SessionListItem(BaseModel):
    session_id: str
    created_at: str
    updated_at: str
    status: SessionStatus
    original_text_preview: str


class HealthResponse(BaseModel):
    status: str
    model_mode: str
    database: str
