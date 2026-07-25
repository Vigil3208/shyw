from __future__ import annotations

import json
import re
from typing import Any

from .schemas import (
    Fact,
    FactValidationItem,
    Platform,
    PlatformValidation,
    ReviewStatus,
    ValidationStatus,
    ValidationSummary,
)


_HIGHLIGHT = re.compile(r"〖([^〖〗]+)〗")
_FACT_NUMBER = re.compile(
    r"(?:\d+(?:\.\d+)?|[一二三四五六七八九十百千万两〇零]+)\s*"
    r"(?:年|月|日|世纪|元|万元|平方米|平米|亩|公顷|公里|千米|米|小时|分钟|点|时)"
)
_EXCLUDED_TEXT_KEYS = {"time_range", "duration_seconds", "position"}


def _content_text(value: Any, key: str | None = None) -> str:
    if key in _EXCLUDED_TEXT_KEYS:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_content_text(item, str(item_key)) for item_key, item in value.items())
    if isinstance(value, list):
        return "\n".join(_content_text(item, key) for item in value)
    return ""


def _format_issues(platform: Platform, content: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if platform == Platform.XIAOHONGSHU:
        if not 5 <= len(content.get("titles", [])) <= 8:
            issues.append("小红书标题数量必须为 5-8 个")
        if not 3 <= len(content.get("tags", [])) <= 5:
            issues.append("小红书话题标签数量必须为 3-5 个")
        if not content.get("body"):
            issues.append("小红书正文不能为空")
    elif platform == Platform.VIDEO:
        duration = content.get("duration_seconds")
        if not isinstance(duration, int) or not 40 <= duration <= 60:
            issues.append("短视频建议时长必须为 40-60 秒")
        if len(content.get("shots", [])) < 5:
            issues.append("短视频脚本至少需要 5 个分镜")
    else:
        body = content.get("body", "")
        if not 50 <= len(body) <= 100:
            issues.append("朋友圈正文必须为 50-100 字")
        if len(content.get("poster_quotes", [])) != 2:
            issues.append("海报金句必须为 2 条")
        grid = content.get("grid", [])
        if len(grid) != 9 or {item.get("position") for item in grid} != set(range(1, 10)):
            issues.append("九宫格方案必须完整包含 1-9 号位置")
    return issues


class FactValidator:
    """独立于生成 Agent 的程序化事实与结构校验器。"""

    def validate_platform(
        self,
        platform: Platform,
        content: dict[str, Any] | None,
        original_text: str,
        facts: list[Fact],
    ) -> PlatformValidation:
        if content is None:
            return PlatformValidation(
                platform=platform,
                status=ValidationStatus.NOT_COMPLETED,
                direct_usable=False,
                fact_coverage=0,
                issues=["该平台内容生成失败，事实校验未完成"],
            )

        text = _content_text(content)
        details: list[FactValidationItem] = []
        used = 0
        allowed_values = {
            value
            for fact in facts
            for value in (fact.source_text, fact.normalized_value)
            if value
        }
        for fact in facts:
            marked_source = f"〖{fact.source_text}〗"
            marked_normalized = f"〖{fact.normalized_value}〗"
            if marked_source in text or marked_normalized in text:
                used += 1
                details.append(
                    FactValidationItem(
                        fact_id=fact.fact_id,
                        source_text=fact.source_text,
                        occurrence=marked_source if marked_source in text else marked_normalized,
                        status="consistent",
                        message="事实已高亮且值与事实库一致",
                    )
                )
            elif fact.source_text in text or fact.normalized_value in text:
                used += 1
                details.append(
                    FactValidationItem(
                        fact_id=fact.fact_id,
                        source_text=fact.source_text,
                        occurrence=fact.source_text,
                        status="unmarked",
                        message="事实值一致，但缺少 〖〗 高亮",
                    )
                )
            else:
                details.append(
                    FactValidationItem(
                        fact_id=fact.fact_id,
                        source_text=fact.source_text,
                        status="not_used",
                        message="本平台内容未使用该事实，不视为篡改",
                    )
                )

        issues = _format_issues(platform, content)
        highlighted_values = set(_HIGHLIGHT.findall(text))
        unknown_highlights = sorted(highlighted_values - allowed_values)
        if unknown_highlights:
            issues.append("存在事实库外的高亮事实：" + "、".join(unknown_highlights))

        allowed_numbers = set(_FACT_NUMBER.findall(original_text))
        output_without_highlights = _HIGHLIGHT.sub("", text)
        added_numbers = sorted(set(_FACT_NUMBER.findall(output_without_highlights)) - allowed_numbers)
        if added_numbers:
            issues.append("存在原文外的数字事实：" + "、".join(added_numbers))

        unmarked = [item.fact_id for item in details if item.status == "unmarked"]
        if unmarked:
            issues.append("以下事实未按要求高亮：" + "、".join(unmarked))

        has_pending = any(fact.review_status == ReviewStatus.PENDING for fact in facts)
        if issues:
            status = ValidationStatus.FAILED
        elif has_pending:
            status = ValidationStatus.PENDING
        else:
            status = ValidationStatus.PASSED
        return PlatformValidation(
            platform=platform,
            status=status,
            direct_usable=status == ValidationStatus.PASSED,
            fact_coverage=(used / len(facts)) if facts else 1.0,
            details=details,
            issues=issues,
        )

    def validate_all(
        self,
        original_text: str,
        facts: list[Fact],
        outputs: dict[Platform, dict[str, Any] | None],
    ) -> ValidationSummary:
        validations = {
            platform.value: self.validate_platform(platform, outputs.get(platform), original_text, facts)
            for platform in Platform
        }
        statuses = {item.status for item in validations.values()}
        if ValidationStatus.FAILED in statuses:
            status = ValidationStatus.FAILED
        elif ValidationStatus.NOT_COMPLETED in statuses:
            status = ValidationStatus.NOT_COMPLETED
        elif ValidationStatus.PENDING in statuses:
            status = ValidationStatus.PENDING
        else:
            status = ValidationStatus.PASSED
        return ValidationSummary(
            status=status,
            direct_usable=all(item.direct_usable for item in validations.values()),
            platforms=validations,
        )


def validation_to_json(summary: ValidationSummary) -> str:
    return json.dumps(summary.model_dump(mode="json"), ensure_ascii=False)
