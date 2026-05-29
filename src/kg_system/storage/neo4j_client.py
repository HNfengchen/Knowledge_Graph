from __future__ import annotations

import uuid
from typing import Any

from neo4j import AsyncDriver, AsyncGraphDatabase

from kg_system.core.config import get_settings
from kg_system.core.exceptions import Neo4jError
from kg_system.core.logging import get_logger
from kg_system.core.models import (
    ExtractedEntity,
    ExtractedRelation,
    GraphLink,
    GraphNode,
    SubgraphResult,
)

log = get_logger(__name__)


class Neo4jClient:
    """异步 Neo4j 客户端。封装 upsert / 子图查询 / 任意 Cypher 执行。"""

    def __init__(self, driver: AsyncDriver, database: str) -> None:
        self._driver = driver
        self._database = database

    @classmethod
    async def create(cls) -> "Neo4jClient":
        s = get_settings()
        driver = AsyncGraphDatabase.driver(
            s.NEO4J_URI,
            auth=(s.NEO4J_USER, s.NEO4J_PASSWORD),
            max_connection_pool_size=s.NEO4J_MAX_CONNECTION_POOL_SIZE,
            connection_timeout=s.NEO4J_CONNECTION_TIMEOUT,
        )
        try:
            await driver.verify_connectivity()
        except Exception as e:
            await driver.close()
            raise Neo4jError(f"failed to connect Neo4j: {e}") from e
        log.info("neo4j_connected", uri=s.NEO4J_URI, database=s.NEO4J_DATABASE)
        return cls(driver, s.NEO4J_DATABASE)

    async def close(self) -> None:
        await self._driver.close()

    async def execute_cypher(self, cypher: str, params: dict | None = None) -> list[dict]:
        async with self._driver.session(database=self._database) as session:
            result = await session.run(cypher, params or {})
            return [record.data() async for record in result]

    async def find_entity_by_name(self, name: str, type: str | None = None) -> GraphNode | None:
        if type:
            cypher = "MATCH (e:Entity {name:$name, type:$type}) RETURN e LIMIT 1"
            params = {"name": name, "type": type}
        else:
            cypher = "MATCH (e:Entity {name:$name}) RETURN e LIMIT 1"
            params = {"name": name}
        rows = await self.execute_cypher(cypher, params)
        if not rows:
            return None
        e = rows[0]["e"]
        return GraphNode(
            id=e.get("id"),
            name=e.get("name"),
            type=e.get("type"),
            props={k: v for k, v in e.items() if k not in {"id", "name", "type", "embedding"}},
        )

    async def upsert_entities(self, entities: list[ExtractedEntity]) -> dict[str, str]:
        """对每个 entity 按 (name,type) merge；返回 name→uuid 映射。"""
        if not entities:
            return {}
        name_to_id: dict[str, str] = {}
        cypher = """
        MERGE (e:Entity {name:$name, type:$type})
        ON CREATE SET e.id=$id, e.created_at=timestamp()
        ON MATCH  SET e.updated_at=timestamp()
        SET e += $props
        RETURN e.id AS id
        """
        async with self._driver.session(database=self._database) as session:
            for ent in entities:
                eid = str(uuid.uuid4())
                params = {
                    "name": ent.name,
                    "type": ent.type,
                    "id": eid,
                    "props": ent.props,
                }
                result = await session.run(cypher, params)
                rec = await result.single()
                name_to_id[ent.name] = rec["id"] if rec else eid
        log.info("entities_upserted", count=len(name_to_id))
        return name_to_id

    async def upsert_relations(
        self,
        relations: list[ExtractedRelation],
        name_to_id: dict[str, str],
    ) -> int:
        """按头尾节点 id + relation_type merge 关系。返回新增/更新数。"""
        if not relations:
            return 0
        cypher = """
        MATCH (h:Entity {id:$head_id})
        MATCH (t:Entity {id:$tail_id})
        MERGE (h)-[r:RELATED_TO {relation_type:$rel}]->(t)
        ON CREATE SET r.id=$rid, r.weight=$weight, r.created_at=timestamp()
        ON MATCH  SET r.weight=$weight, r.updated_at=timestamp()
        SET r += $props
        RETURN r.id AS rid
        """
        count = 0
        async with self._driver.session(database=self._database) as session:
            for rel in relations:
                head_id = name_to_id.get(rel.head)
                tail_id = name_to_id.get(rel.tail)
                if not head_id or not tail_id:
                    continue
                params = {
                    "head_id": head_id,
                    "tail_id": tail_id,
                    "rel": rel.relation,
                    "rid": str(uuid.uuid4()),
                    "weight": rel.weight,
                    "props": rel.props,
                }
                await session.run(cypher, params)
                count += 1
        log.info("relations_upserted", count=count)
        return count

    async def match_subgraph(
        self,
        entity_name: str,
        depth: int,
        relation_types: list[str] | None = None,
    ) -> SubgraphResult:
        """返回以 entity_name 为中心、深度 depth 的子图，转 D3 friendly 结构。"""
        depth = max(1, min(depth, 3))
        if relation_types:
            where_rel = " AND ALL(rr IN relationships(p) WHERE rr.relation_type IN $rel_types)"
        else:
            where_rel = ""
        cypher = f"""
        MATCH p=(e:Entity {{name:$name}})-[r:RELATED_TO*1..{depth}]-(n:Entity)
        WHERE 1=1 {where_rel}
        WITH nodes(p) AS ns, relationships(p) AS rs
        UNWIND ns AS n
        WITH collect(DISTINCT n) AS nodes_all, rs
        UNWIND rs AS r
        WITH nodes_all, collect(DISTINCT r) AS rels_all
        RETURN nodes_all, rels_all
        """
        params: dict[str, Any] = {"name": entity_name}
        if relation_types:
            params["rel_types"] = relation_types
        rows = await self.execute_cypher(cypher, params)
        if not rows:
            return SubgraphResult()
        row = rows[0]
        nodes = [
            GraphNode(
                id=n.get("id"),
                name=n.get("name"),
                type=n.get("type"),
                props={
                    k: v
                    for k, v in n.items()
                    if k not in {"id", "name", "type", "embedding"}
                },
            )
            for n in row["nodes_all"]
        ]
        links: list[GraphLink] = []
        for r in row["rels_all"]:
            start_id = r.start_node.get("id") if hasattr(r, "start_node") else r.get("start_id")
            end_id = r.end_node.get("id") if hasattr(r, "end_node") else r.get("end_id")
            links.append(
                GraphLink(
                    source=start_id,
                    target=end_id,
                    relation=r.get("relation_type", "RELATED_TO"),
                    weight=r.get("weight", 1.0),
                )
            )
        return SubgraphResult(nodes=nodes, links=links)
