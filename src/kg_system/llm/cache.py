from __future__ import annotations

from typing import Any

from kg_system.core.logging import get_logger

log = get_logger(__name__)


class SemanticCache:
    """语义缓存接口。骨架实现：直通（不缓存），以便后续替换为 embedding+向量检索。"""

    async def get(self, prompt: str) -> str | None:
        return None

    async def set(self, prompt: str, response: str, metadata: dict[str, Any] | None = None) -> None:
        # 占位：将来写入 Redis + 向量索引
        return None
