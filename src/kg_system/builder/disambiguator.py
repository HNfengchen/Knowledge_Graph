from __future__ import annotations

from dataclasses import dataclass

from kg_system.core.config import get_settings
from kg_system.core.logging import get_logger
from kg_system.core.models import ExtractedEntity, GraphNode
from kg_system.llm.factory import get_embedding_model
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


@dataclass
class _Candidate:
    node: GraphNode
    vector_score: float = 0.0
    fulltext_score: float = 0.0
    levenshtein_score: float = 0.0
    type_match: bool = False


class Disambiguator:
    """实体消歧：embedding → 向量召回 → 全文召回 → rerank → 合并 props。

    退化策略：向量索引不可用时回退到 (name,type) 完全匹配。
    """

    def __init__(self, neo4j: Neo4jClient, embedding_model=None) -> None:
        self._neo4j = neo4j
        self._embedding_model = embedding_model
        self._settings = get_settings()

    async def _get_embedding(self, text: str) -> list[float] | None:
        if self._embedding_model is None:
            try:
                self._embedding_model = get_embedding_model()
            except Exception as e:
                log.warning("embedding_model_unavailable", error=str(e))
                return None
        try:
            return await self._embedding_model.aembed_query(text)
        except Exception as e:
            log.warning("embedding_failed", error=str(e))
            return None

    def _levenshtein(self, a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        m, n = len(a), len(b)
        dp = list(range(n + 1))
        for i in range(1, m + 1):
            prev = dp[0]
            dp[0] = i
            for j in range(1, n + 1):
                temp = dp[j]
                cost = 0 if a[i - 1] == b[j - 1] else 1
                dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + cost)
                prev = temp
        return 1.0 - dp[n] / max(m, n)

    def _rerank(
        self,
        entity: ExtractedEntity,
        vector_candidates: list[GraphNode],
        vector_scores: dict[str, float],
        fulltext_candidates: list[GraphNode],
    ) -> list[_Candidate]:
        seen: dict[str, _Candidate] = {}
        for vc in vector_candidates:
            cand = _Candidate(
                node=vc,
                vector_score=vector_scores.get(vc.name, 0.0),
                type_match=vc.type == entity.type,
            )
            cand.levenshtein_score = self._levenshtein(entity.name, vc.name)
            seen[vc.name] = cand
        for fc in fulltext_candidates:
            if fc.name in seen:
                seen[fc.name].fulltext_score = 0.5
            else:
                cand = _Candidate(
                    node=fc,
                    fulltext_score=0.5,
                    type_match=fc.type == entity.type,
                )
                cand.levenshtein_score = self._levenshtein(entity.name, fc.name)
                seen[fc.name] = cand
        scored = list(seen.values())
        for c in scored:
            c.vector_score = min(c.vector_score, 1.0)
            c.fulltext_score = min(c.fulltext_score, 1.0)
            c.levenshtein_score = min(c.levenshtein_score, 1.0)
        scored.sort(
            key=lambda c: (
                c.vector_score * 0.4 + c.fulltext_score * 0.2
                + c.levenshtein_score * 0.2 + (0.2 if c.type_match else 0.0)
            ),
            reverse=True,
        )
        return scored

    def _merge_props(
        self, existing: dict | None, incoming: dict
    ) -> dict:
        if not existing:
            return dict(incoming)
        merged = dict(existing)
        for k, v in incoming.items():
            if k not in merged:
                merged[k] = v
        return merged

    async def resolve(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        if not entities:
            return []
        s = self._settings
        threshold_high = s.ENTITY_SIMILARITY_THRESHOLD + 0.05
        threshold_low = s.ENTITY_SIMILARITY_THRESHOLD - 0.15

        out: list[ExtractedEntity] = []
        strategy = "vector"

        for ent in entities:
            # 1) 先尝试 (name,type) 完全匹配（兜底）
            existing = await self._neo4j.find_entity_by_name(ent.name, ent.type)
            if existing is not None:
                merged_props = self._merge_props(existing.props, ent.props)
                out.append(
                    ExtractedEntity(
                        name=ent.name,
                        type=ent.type,
                        props=merged_props,
                        source_chunk_id=ent.source_chunk_id,
                    )
                )
                continue

            # 2) 向量 + 全文召回
            vector_candidates: list[GraphNode] = []
            fulltext_candidates: list[GraphNode] = []
            vector_scores: dict[str, float] = {}

            if strategy == "vector":
                embedding = await self._get_embedding(
                    f"{ent.name} {ent.type}"
                )
                if embedding is not None:
                    vc_rows = await self._neo4j.vector_search_entities(
                        embedding, top_k=10, threshold=threshold_low
                    )
                    for vc in vc_rows:
                        vector_candidates.append(vc)
                else:
                    strategy = "fulltext_only"

            if strategy != "fulltext_only":
                try:
                    ft_rows = await self._neo4j.fulltext_search_entities(
                        ent.name, top_k=10
                    )
                    fulltext_candidates.extend(ft_rows)
                except Exception:
                    log.warning("fulltext_search_failed", name=ent.name)

            # 3) 如果有向量结果但没记录分数，从结果重建
            if vector_candidates and not vector_scores:
                pass  # 分数已在 vector_search_entities 中无法直接获取

            candidates = self._rerank(
                ent, vector_candidates, vector_scores, fulltext_candidates
            )

            # 4) 决策
            if not candidates:
                out.append(ent)
                continue

            best = candidates[0]
            combined_score = (
                best.vector_score * 0.4 + best.fulltext_score * 0.2
                + best.levenshtein_score * 0.2 + (0.2 if best.type_match else 0.0)
            )

            if combined_score >= threshold_high and best.type_match:
                merged_props = self._merge_props(best.node.props, ent.props)
                out.append(
                    ExtractedEntity(
                        name=best.node.name,
                        type=best.node.type,
                        props=merged_props,
                        source_chunk_id=ent.source_chunk_id,
                    )
                )
            elif combined_score >= threshold_low and best.type_match:
                merged_props = self._merge_props(best.node.props, ent.props)
                out.append(
                    ExtractedEntity(
                        name=best.node.name,
                        type=best.node.type,
                        props=merged_props,
                        source_chunk_id=ent.source_chunk_id,
                    )
                )
            else:
                out.append(ent)

        log.info(
            "disambiguator_resolved",
            input=len(entities),
            output=len(out),
            strategy=strategy,
        )
        return out
