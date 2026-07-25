from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .schemas import Criticality, Fact, FactType, ReviewStatus


_NUMBER = r"(?:\d+(?:\.\d+)?|[一二三四五六七八九十百千万两〇零]+)"


@dataclass(frozen=True, slots=True)
class _Candidate:
    start: int
    end: int
    type: FactType
    priority: int


_PATTERNS: tuple[tuple[FactType, int, re.Pattern[str]], ...] = (
    (
        FactType.OPENING_HOURS,
        100,
        re.compile(
            r"(?:开放(?:时间)?|营业(?:时间)?)[：:]?\s*"
            r"\d{1,2}[：:]\d{2}\s*(?:[-—至到]\s*\d{1,2}[：:]\d{2})?"
        ),
    ),
    (
        FactType.PRICE,
        95,
        re.compile(rf"(?:门票|票价|成人票|优惠票)[：:]?\s*(?:{_NUMBER}\s*元|免费)"),
    ),
    (
        FactType.DATE,
        90,
        re.compile(rf"(?:公元前\s*)?{_NUMBER}\s*(?:年|世纪)(?:{_NUMBER}\s*月(?:{_NUMBER}\s*日)?)?"),
    ),
    (
        FactType.ERA,
        88,
        re.compile(
            r"(?:夏|商|周|秦|汉|晋|隋|唐|宋|元|明|清)(?:代|朝)|"
            r"(?:春秋|战国|三国|南北朝|民国)时期?"
        ),
    ),
    (
        FactType.AREA,
        85,
        re.compile(rf"{_NUMBER}\s*(?:平方千米|平方公里|平方米|平米|公顷|亩)"),
    ),
    (
        FactType.NUMBER,
        60,
        re.compile(
            rf"{_NUMBER}\s*(?:公里|千米|米|层|座|处|件|尊|级|步|小时|分钟|万人|人)"
        ),
    ),
    (
        FactType.ORGANIZATION,
        55,
        re.compile(r"[\u4e00-\u9fff]{2,20}(?:博物馆|研究院|委员会|管理局|协会|公司)"),
    ),
    (
        FactType.PLACE,
        50,
        re.compile(
            r"[\u4e00-\u9fff]{2,12}(?:省|市|区|县|镇|乡|村|山|湖|河|寺|宫|殿|阁|楼|桥|城|景区|故居|遗址)"
        ),
    ),
    (
        FactType.PERSON,
        45,
        re.compile(
            r"(?:由|人物是|名人是|作者是|设计者是|主持者是)\s*"
            r"[\u4e00-\u9fff]{2,4}|[\u4e00-\u9fff]{2,4}(?:先生|女士|将军|皇帝|诗人|建筑师)"
        ),
    ),
)


def _criticality(fact_type: FactType) -> Criticality:
    if fact_type in {
        FactType.ERA,
        FactType.DATE,
        FactType.PERSON,
        FactType.PLACE,
        FactType.ORGANIZATION,
        FactType.PRICE,
        FactType.OPENING_HOURS,
    }:
        return Criticality.CRITICAL
    return Criticality.GENERAL


def extract_facts_locally(text: str) -> list[Fact]:
    """保守的离线事实抽取器；生产模式由结构化模型补足语义事实。"""
    candidates: list[_Candidate] = []
    for fact_type, priority, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            candidates.append(_Candidate(match.start(), match.end(), fact_type, priority))

    selected: list[_Candidate] = []
    for candidate in sorted(candidates, key=lambda item: (-item.priority, item.start, -item.end)):
        if any(candidate.start < item.end and item.start < candidate.end for item in selected):
            continue
        selected.append(candidate)

    selected.sort(key=lambda item: (item.start, item.end))
    facts: list[Fact] = []
    for index, item in enumerate(selected, start=1):
        source = text[item.start : item.end].strip()
        facts.append(
            Fact(
                fact_id=f"F{index:03d}",
                type=item.type,
                source_text=source,
                normalized_value=source,
                source_start=item.start,
                source_end=item.end,
                criticality=_criticality(item.type),
                review_status=ReviewStatus.CONFIRMED,
            )
        )
    return facts


def normalize_model_facts(text: str, facts: Iterable[Fact]) -> list[Fact]:
    """只接受能逐字回溯原文的模型事实，并由服务端重建 ID 与位置。"""
    normalized: list[Fact] = []
    seen: set[tuple[int, int, str]] = set()
    cursor_by_source: dict[str, int] = {}
    for fact in facts:
        source = fact.source_text.strip()
        if not source:
            continue
        start_at = cursor_by_source.get(source, 0)
        start = text.find(source, start_at)
        if start < 0:
            start = text.find(source)
        if start < 0:
            continue
        end = start + len(source)
        key = (start, end, fact.type.value)
        if key in seen:
            continue
        seen.add(key)
        cursor_by_source[source] = end
        normalized.append(
            fact.model_copy(
                update={
                    "fact_id": "",
                    "source_text": source,
                    "normalized_value": fact.normalized_value.strip() or source,
                    "source_start": start,
                    "source_end": end,
                }
            )
        )
    normalized.sort(key=lambda item: (item.source_start, item.source_end))
    return [fact.model_copy(update={"fact_id": f"F{i:03d}"}) for i, fact in enumerate(normalized, 1)]


def highlight_facts(text: str, facts: Iterable[Fact]) -> str:
    """在不重复嵌套标记的前提下高亮事实原文。"""
    result = text
    unique = {fact.source_text for fact in facts if fact.source_text}
    for index, source in enumerate(sorted(unique, key=len, reverse=True)):
        marked = f"〖{source}〗"
        placeholder = f"\x00FACT_{index}\x00"
        result = result.replace(marked, placeholder)
        result = result.replace(source, marked)
        result = result.replace(placeholder, marked)
    return result


_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("中国大陆手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("身份证号", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("电子邮箱", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
)


def detect_sensitive_information(text: str) -> list[str]:
    return [name for name, pattern in _PII_PATTERNS if pattern.search(text)]
