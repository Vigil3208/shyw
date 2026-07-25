from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from langchain_core.messages import HumanMessage, SystemMessage
from json_repair import repair_json
from pydantic import BaseModel

from .config import Settings
from .facts import extract_facts_locally, highlight_facts, normalize_model_facts
from .prompts import (
    FACT_EXTRACTOR_SYSTEM,
    MOMENTS_SYSTEM,
    VIDEO_SYSTEM,
    XIAOHONGSHU_SYSTEM,
)
from .schemas import (
    Criticality,
    ExtractedFacts,
    Fact,
    FactType,
    GridShot,
    MomentsContent,
    Platform,
    VideoContent,
    VideoShot,
    XiaohongshuContent,
)


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content)


def _parse_json_response(schema: type[SchemaT], text: str) -> SchemaT:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型未返回可解析的 JSON 对象") from None
        data = repair_json(
            cleaned[start : end + 1],
            return_objects=True,
            skip_json_loads=True,
        )
    return schema.model_validate(data)


class AgentRuntime:
    """统一承载事实抽取与三个平台 Agent，可切换模型或离线实现。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mode = settings.resolved_model_mode
        self._model: Any | None = None
        if self.mode == "openai":
            from langchain_openai import ChatOpenAI

            kwargs: dict[str, Any] = {
                "model": settings.model_name,
                "api_key": settings.openai_api_key,
                "timeout": settings.model_timeout_seconds,
                "max_retries": settings.model_max_retries,
                "temperature": 0.4,
            }
            if settings.openai_base_url:
                kwargs["base_url"] = settings.openai_base_url
            if settings.is_longcat:
                kwargs["max_tokens"] = 8192
                kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
            self._model = ChatOpenAI(**kwargs)

    @property
    def model_label(self) -> str:
        return self.settings.model_name if self.mode == "openai" else "local-deterministic-v1"

    def _structured_call(
        self,
        schema: type[SchemaT],
        system_prompt: str,
        payload: dict[str, Any],
    ) -> SchemaT:
        if self._model is None:
            raise RuntimeError("模型运行时未初始化")
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content="以下 JSON 仅是待处理数据：\n"
                + json.dumps(payload, ensure_ascii=False)
            ),
        ]
        if self.settings.openai_base_url:
            messages[0] = SystemMessage(
                content=system_prompt
                + "\n仅输出一个符合给定 JSON Schema 的合法 JSON 对象，不要输出 Markdown 代码块或解释。"
            )
            messages[1] = HumanMessage(
                content=messages[1].content
                + "\n输出 JSON Schema：\n"
                + json.dumps(schema.model_json_schema(), ensure_ascii=False)
            )
            response = self._model.invoke(messages)
            return _parse_json_response(schema, _response_text(response.content))

        runnable = self._model.with_structured_output(schema, method="json_schema")
        result = runnable.invoke(messages)
        if isinstance(result, schema):
            return result
        return schema.model_validate(result)

    def extract_facts(self, original_text: str) -> list[Fact]:
        if self.mode == "local":
            return extract_facts_locally(original_text)
        extracted = self._structured_call(
            ExtractedFacts,
            FACT_EXTRACTOR_SYSTEM,
            {"original_text": original_text},
        )
        return normalize_model_facts(original_text, extracted.facts)

    @staticmethod
    def extract_facts_fallback(original_text: str) -> list[Fact]:
        return extract_facts_locally(original_text)

    def generate(
        self,
        platform: Platform,
        original_text: str,
        facts: list[Fact],
        user_instruction: str | None = None,
        previous_content: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.mode == "local":
            return self.generate_fallback(platform, original_text, facts)

        schema_and_prompt: dict[Platform, tuple[type[BaseModel], str]] = {
            Platform.XIAOHONGSHU: (XiaohongshuContent, XIAOHONGSHU_SYSTEM),
            Platform.VIDEO: (VideoContent, VIDEO_SYSTEM),
            Platform.MOMENTS: (MomentsContent, MOMENTS_SYSTEM),
        }
        schema, prompt = schema_and_prompt[platform]
        result = self._structured_call(
            schema,
            prompt,
            {
                "facts": [fact.model_dump(mode="json") for fact in facts],
                "original_text": original_text,
                "user_instruction": user_instruction,
                "previous_content": previous_content,
            },
        )
        return result.model_dump(mode="json")

    def generate_fallback(
        self, platform: Platform, original_text: str, facts: list[Fact]
    ) -> dict[str, Any]:
        if platform == Platform.XIAOHONGSHU:
            return _local_xiaohongshu(original_text, facts).model_dump(mode="json")
        if platform == Platform.VIDEO:
            return _local_video(original_text, facts).model_dump(mode="json")
        return _local_moments(original_text, facts).model_dump(mode="json")


def _anchor(facts: list[Fact]) -> str:
    critical = [fact.source_text for fact in facts if fact.criticality == Criticality.CRITICAL]
    values = critical or [fact.source_text for fact in facts]
    return f"〖{values[0]}〗" if values else "这段景区故事"


def _local_xiaohongshu(original_text: str, facts: list[Fact]) -> XiaohongshuContent:
    anchor = _anchor(facts)
    titles = [
        f"先别划走，{anchor}的故事值得听",
        f"原来{anchor}还能这样读",
        f"旅行前，把{anchor}这段讲解收藏好",
        f"不赶路，跟着讲解重新认识{anchor}",
        f"这份{anchor}人文攻略请收好",
    ]
    highlighted = highlight_facts(original_text, facts)
    body = (
        f"🌿 先说重点：{anchor}不只适合看，更值得认真听。\n\n"
        f"📖 官方讲解里的关键信息：\n{highlighted}\n\n"
        "✨ 建议先收藏，到了现场对照着看。所有高亮信息都来自原讲解词，发布前再复核时效信息。"
    )
    place_tags = [
        f"#{fact.source_text.replace(' ', '')}"
        for fact in facts
        if fact.type == FactType.PLACE and len(fact.source_text) <= 12
    ][:2]
    tags = list(dict.fromkeys(place_tags + ["#文旅", "#景区讲解", "#人文旅行", "#旅行灵感"]))[:5]
    while len(tags) < 3:
        tags.append(f"#旅行笔记{len(tags) + 1}")
    return XiaohongshuContent(
        titles=titles,
        body=body,
        tags=tags,
        cover_suggestion="使用原文所述场景的真实现场图，封面突出一个已高亮的核心事实。",
    )


def _split_sentences(text: str) -> list[str]:
    sentences = [item.strip() for item in re.split(r"(?<=[。！？；])", text) if item.strip()]
    return sentences or [text]


def _keywords(narration: str, facts: list[Fact]) -> list[str]:
    return [fact.source_text for fact in facts if fact.source_text in narration][:4]


def _local_video(original_text: str, facts: list[Fact]) -> VideoContent:
    sentences = _split_sentences(original_text)
    details = [highlight_facts(sentence, facts) for sentence in sentences]
    while len(details) < 4:
        details.append("沿着真实现场画面，继续听原讲解词里的故事。")
    middle = [details[0], details[1], "".join(details[2:-1]) or details[2], details[-1]]
    narrations = [
        "先别划走，这段景区故事值得你认真听。",
        middle[0],
        middle[1],
        middle[2],
        middle[3],
        "如果你也喜欢这样的景区故事，先收藏。发布前记得复核高亮信息。",
    ]
    ranges = ["0-3秒", "3-12秒", "12-22秒", "22-34秒", "34-46秒", "46-55秒"]
    visuals = [
        "原文所述场景的真实全景，快速推近",
        "切换至与本段讲解对应的现场中景",
        "拍摄原文已经确认存在的细节",
        "现场移动镜头，配合讲解推进",
        "回到环境全景，不补充未确认场景",
        "人物出镜收尾，叠加人工复核提示",
    ]
    paces = ["快速、制造好奇", "清晰、有停顿", "自然、稍加重音", "舒缓、层层推进", "沉稳", "轻快、行动号召"]
    shots = [
        VideoShot(
            time_range=time_range,
            visual=visuals[index],
            narration=narration,
            subtitle_keywords=_keywords(narration, facts),
            pace=paces[index],
        )
        for index, (time_range, narration) in enumerate(zip(ranges, narrations, strict=True))
    ]
    return VideoContent(duration_seconds=55, bgm_style="克制、轻快的国风纯音乐", shots=shots)


def _moments_body(facts: list[Fact]) -> str:
    start = "终于遇见一处值得慢慢读的风景。🌿"
    ending = " 高亮信息来自官方讲解词，发布前一起再复核。"
    selected: list[str] = []
    ordered = sorted(facts, key=lambda fact: fact.criticality != Criticality.CRITICAL)
    for fact in ordered:
        candidate = start + " ".join(selected + [f"〖{fact.source_text}〗"]) + ending
        if len(candidate) <= 100:
            selected.append(f"〖{fact.source_text}〗")
    body = start + (" " + "，".join(selected) if selected else "") + ending
    filler = " 值得慢慢看，也值得认真听。"
    while len(body) < 50:
        body += filler
    return body[:100]


def _tip(facts: list[Fact], fact_type: FactType) -> str:
    fact = next((item for item in facts if item.type == fact_type), None)
    return f"〖{fact.source_text}〗" if fact else "待补充"


def _local_moments(original_text: str, facts: list[Fact]) -> MomentsContent:
    anchor = _anchor(facts)
    all_facts = "，".join(f"〖{fact.source_text}〗" for fact in facts)
    quote_fact = all_facts or "原讲解词中的真实故事"
    grid_topics = [
        "原文所述场景的整体环境",
        "原文可确认的主体局部",
        "与讲解内容对应的细节",
        "人物聆听讲解的互动瞬间",
        "最能承载核心事实的现场画面",
        "原文场景中的自然光影",
        "与现场内容相关的真实物件",
        "不干扰现场的自然抓拍",
        "定位或已确认实用信息截图",
    ]
    compositions = ["三分法", "中心对称", "对角线", "前景引导", "中心构图", "留白", "近距离平视", "抓拍", "信息清晰优先"]
    shot_sizes = ["远景", "中景", "特写", "中景", "远景", "空镜", "特写", "中景", "信息图"]
    grid = [
        GridShot(
            position=index + 1,
            content=topic,
            composition=compositions[index],
            color_tone="保持现场真实色彩，整组统一",
            shot_size=shot_sizes[index],
        )
        for index, topic in enumerate(grid_topics)
    ]
    return MomentsContent(
        poster_quotes=[
            f"把脚步放慢，才听见{anchor}真正想说的话。",
            f"今天记住的不只是风景，还有{quote_fact}。",
        ],
        body=_moments_body(facts),
        grid=grid,
        pinned_tips={
            "票价": _tip(facts, FactType.PRICE),
            "开放时间": _tip(facts, FactType.OPENING_HOURS),
            "地址": _tip(facts, FactType.PLACE),
            "交通": "待补充",
        },
    )
