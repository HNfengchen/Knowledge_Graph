from __future__ import annotations

import json
from pathlib import Path

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from kg_system.core.config import get_settings
from kg_system.core.exceptions import LLMError
from kg_system.core.logging import get_logger
from kg_system.core.models import ExtractedEntity, ExtractedRelation

log = get_logger(__name__)


class _EntitiesPayload(BaseModel):
    entities: list[ExtractedEntity]


class _RelationsPayload(BaseModel):
    relations: list[ExtractedRelation]


def _read_prompt(primary_path: str, fallback_relative: str) -> str:
    p = Path(primary_path)
    if p.is_file():
        return p.read_text(encoding="utf-8")
    fb = Path(fallback_relative)
    if fb.is_file():
        return fb.read_text(encoding="utf-8")
    raise FileNotFoundError(f"prompt not found: {primary_path} (fallback {fallback_relative})")


def _parse_json_strict(content: str) -> dict:
    """LLM 偶尔会包 markdown 代码块；剥掉再 json.loads。"""
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    return json.loads(text)


class EntityExtractor:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm
        s = get_settings()
        self._prompt_tpl = _read_prompt(
            s.ENTITY_EXTRACTION_PROMPT_TEMPLATES,
            "prompts/entity_extraction.txt",
        )
        self._entity_types = ",".join(s.entity_types_list)

    async def extract(self, chunk: str) -> list[ExtractedEntity]:
        prompt = self._prompt_tpl.format(text=chunk, entity_types=self._entity_types)
        try:
            msg = await self._llm.ainvoke([HumanMessage(content=prompt)])
        except Exception as e:
            raise LLMError(f"entity extraction LLM call failed: {e}") from e
        try:
            payload = _EntitiesPayload(**_parse_json_strict(str(msg.content)))
        except (json.JSONDecodeError, ValidationError) as e:
            log.warning("entity_parse_failed", error=str(e), raw=str(msg.content)[:200])
            return []
        return payload.entities


class RelationExtractor:
    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm
        s = get_settings()
        self._prompt_tpl = _read_prompt(
            s.RELATION_EXTRACTION_PROMPT_TEMPLATES,
            "prompts/relation_extraction.txt",
        )
        self._relation_types = ",".join(s.relation_types_list)

    async def extract(
        self, chunk: str, entities: list[ExtractedEntity]
    ) -> list[ExtractedRelation]:
        if not entities:
            return []
        entities_str = json.dumps(
            [{"name": e.name, "type": e.type} for e in entities], ensure_ascii=False
        )
        prompt = self._prompt_tpl.format(
            text=chunk,
            entities=entities_str,
            relation_types=self._relation_types,
        )
        try:
            msg = await self._llm.ainvoke([HumanMessage(content=prompt)])
        except Exception as e:
            raise LLMError(f"relation extraction LLM call failed: {e}") from e
        try:
            payload = _RelationsPayload(**_parse_json_strict(str(msg.content)))
        except (json.JSONDecodeError, ValidationError) as e:
            log.warning("relation_parse_failed", error=str(e), raw=str(msg.content)[:200])
            return []
        valid_names = {e.name for e in entities}
        return [r for r in payload.relations if r.head in valid_names and r.tail in valid_names]
