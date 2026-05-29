from __future__ import annotations

from kg_system.core.logging import get_logger
from kg_system.core.models import SubgraphResult
from kg_system.storage.neo4j_client import Neo4jClient

log = get_logger(__name__)


class KGQueryService:
    """业务侧/外部 LLM 调用图谱的统一入口。"""

    def __init__(self, neo4j: Neo4jClient) -> None:
        self._neo4j = neo4j

    async def query_subgraph(
        self,
        entity_name: str,
        depth: int = 2,
        relation_types: list[str] | None = None,
    ) -> SubgraphResult:
        return await self._neo4j.match_subgraph(entity_name, depth, relation_types)

    async def get_entity_context(self, entity_name: str, max_neighbors: int = 10) -> str:
        """以 1-hop 邻居拼出文本上下文。骨架实现：简单字符串拼接。"""
        sg = await self._neo4j.match_subgraph(entity_name, depth=1)
        if not sg.nodes:
            return f"未找到实体 {entity_name}。"
        center = next((n for n in sg.nodes if n.name == entity_name), sg.nodes[0])
        lines = [f"实体: {center.name} (类型: {center.type})"]
        if center.props:
            lines.append(f"属性: {center.props}")
        neighbors = [n for n in sg.nodes if n.id != center.id][:max_neighbors]
        if neighbors:
            lines.append("相关实体:")
            for n in neighbors:
                rel = next(
                    (
                        l
                        for l in sg.links
                        if (l.source == center.id and l.target == n.id)
                        or (l.target == center.id and l.source == n.id)
                    ),
                    None,
                )
                rel_label = rel.relation if rel else "RELATED_TO"
                lines.append(f"  - [{rel_label}] {n.name} ({n.type})")
        return "\n".join(lines)
